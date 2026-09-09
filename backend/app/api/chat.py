"""Chat endpoints: GET /api/chat/history, POST /api/chat.

See planning/API_CONTRACT.md "POST /api/chat" for the full frozen request/
response contract, and planning/LLM_DESIGN.md for the system prompt,
structured output schema, context/history budget, and mock catalogue this
handler is built against.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.db import add_chat_message, get_chat_history, get_watchlist
from app.llm import (
    LLMCallError,
    LLMParseError,
    build_messages,
    build_mock_raw_response,
    build_portfolio_context,
    call_llm,
    execute_trades,
    execute_watchlist_changes,
    has_api_key,
    is_mock_mode,
    parse_llm_response,
)
from app.llm.schema import LLMChatResponse
from app.market import MarketDataSource, PriceCache
from app.portfolio import snapshot_once, sync_tracked_tickers

from .deps import get_market_source, get_price_cache
from .portfolio import build_portfolio_response
from .schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# PLAN §13.B10: bound chat context/history at 20 messages. Reused as the
# GET /api/chat/history default too, so the two never drift apart.
DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 200

NOT_CONFIGURED_DETAIL = (
    "The AI assistant is not configured: OPENROUTER_API_KEY is missing. Set it "
    "in the project .env (or set LLM_MOCK=true for testing) and restart."
)
UPSTREAM_FAILURE_DETAIL = (
    "The AI assistant failed to produce a response. Please try again in a moment."
)


@router.get("/history")
async def chat_history(limit: int = DEFAULT_HISTORY_LIMIT) -> dict:
    limit = max(1, min(limit, MAX_HISTORY_LIMIT))
    messages = await get_chat_history(limit=limit)
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "actions": json.loads(m.actions) if m.actions else None,
                "created_at": m.created_at,
            }
            for m in messages
        ]
    }


async def _watchlist_items() -> list[dict]:
    """Bare array of {ticker, added_at} -- matches POST /api/portfolio/reset's
    "watchlist" field shape (not GET /api/watchlist's {"watchlist": [...]}
    wrapper), per the ruling resolving the ambiguity in the original contract
    text: every mutating endpoint returns updated state in one consistent,
    unwrapped shape (C2)."""
    items = await get_watchlist()
    return [{"ticker": w.ticker, "added_at": w.added_at} for w in items]


@router.post("")
async def chat(
    body: ChatRequest,
    price_cache: PriceCache = Depends(get_price_cache),
    market_source: MarketDataSource = Depends(get_market_source),
) -> dict:
    # B11: still boot/stream/trade fine without a key; only /api/chat is
    # degraded, and only when not in mock mode. Nothing is persisted here
    # -- the user's message never entered the model's context.
    if not is_mock_mode() and not has_api_key():
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_DETAIL)

    # Load history BEFORE persisting the new user message, so the prompt
    # is [system] + [prior turns] + [this message] with no duplication.
    history = await get_chat_history(limit=DEFAULT_HISTORY_LIMIT)
    context = await build_portfolio_context(price_cache)

    # The user's own message is persisted regardless of what happens next
    # -- only a genuine model response earns an assistant turn (see below).
    await add_chat_message(role="user", content=body.message)

    if is_mock_mode():
        raw = build_mock_raw_response(body.message, context)
    else:
        messages = build_messages(context, history, body.message)
        try:
            raw = call_llm(messages)
        except LLMCallError as exc:
            logger.exception("LLM call failed")
            raise HTTPException(status_code=502, detail=UPSTREAM_FAILURE_DETAIL) from exc

    try:
        parsed: LLMChatResponse = parse_llm_response(raw)
    except LLMParseError as exc:
        logger.warning("Failed to parse LLM response: %r", raw)
        raise HTTPException(status_code=502, detail=UPSTREAM_FAILURE_DETAIL) from exc

    trades_executed, trades_failed = await execute_trades(parsed.trades, price_cache)
    watchlist_changes = await execute_watchlist_changes(parsed.watchlist_changes)

    # Mirror POST /api/portfolio/trade's side effects (A4, §7), run once
    # for the whole batch rather than per-action.
    if trades_executed or watchlist_changes:
        await sync_tracked_tickers(market_source)
    if trades_executed:
        await snapshot_once(price_cache)

    actions: dict = {}
    if trades_executed:
        actions["trades_executed"] = trades_executed
    if trades_failed:
        actions["trades_failed"] = trades_failed
    if watchlist_changes:
        actions["watchlist_changes"] = watchlist_changes

    await add_chat_message(
        role="assistant",
        content=parsed.message,
        actions=json.dumps(actions) if actions else None,
    )

    portfolio = await build_portfolio_response(price_cache)
    watchlist = await _watchlist_items()

    return {
        "message": parsed.message,
        "trades_executed": trades_executed,
        "trades_failed": trades_failed,
        "watchlist_changes": watchlist_changes,
        "portfolio": portfolio,
        "watchlist": watchlist,
    }
