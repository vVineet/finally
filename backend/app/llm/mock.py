"""Deterministic mock responses for `LLM_MOCK=true` (PLAN §5, §13).

No network call. Produces the same `LLMChatResponse` shape a real call
would, from simple keyword pattern-matching over the raw message -- not
NLU. See planning/LLM_DESIGN.md §7 for the exact grammar and canonical
trigger phrases the Integration Tester should use.

Whether a matched trade/watchlist change ultimately succeeds or fails is
decided by the real executor against real DB/price-cache state (exactly
like a real model's output would be) -- this module only extracts intent,
never decides outcomes.
"""

from __future__ import annotations

import re

from .context import PortfolioContext
from .schema import LLMChatResponse, LLMTrade, LLMWatchlistChange

_TRADE_RE = re.compile(
    r"\b(?P<side>buy|sell)\b\s*(?P<quantity>\d+(?:\.\d+)?)?\s*"
    r"(?:shares?\s+(?:of\s+)?)?(?P<ticker>[A-Za-z]{1,10}(?:\.[A-Za-z]{1,2})?)\b",
    re.IGNORECASE,
)

_WATCHLIST_KEYWORD_RE = re.compile(r"\bwatchlist\b", re.IGNORECASE)
_WATCHLIST_ADD_RE = re.compile(r"\badd\b", re.IGNORECASE)
_WATCHLIST_REMOVE_RE = re.compile(r"\b(remove|delete|drop)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z]{1,10}(?:\.[A-Za-z]{1,2})?")

_TICKER_STOPWORDS = {
    "SHARE", "SHARES", "OF", "STOCK", "STOCKS", "SOME", "MORE", "THE", "MY",
    "TO", "FROM", "IT", "PLEASE", "A", "AN", "AND", "FOR", "ME", "IN", "ALL",
    "ANY", "THIS", "THAT", "OUR", "YOUR",
}
_WATCHLIST_STOPWORDS = _TICKER_STOPWORDS | {"ADD", "REMOVE", "DELETE", "DROP", "WATCHLIST"}


def _extract_trade(message: str) -> LLMTrade | None:
    for match in _TRADE_RE.finditer(message):
        ticker = match.group("ticker").upper()
        if ticker in _TICKER_STOPWORDS:
            continue
        quantity = float(match.group("quantity")) if match.group("quantity") else 1.0
        return LLMTrade(ticker=ticker, side=match.group("side").lower(), quantity=quantity)
    return None


def _extract_watchlist_change(message: str) -> LLMWatchlistChange | None:
    if not _WATCHLIST_KEYWORD_RE.search(message):
        return None
    if _WATCHLIST_REMOVE_RE.search(message):
        action = "remove"
    elif _WATCHLIST_ADD_RE.search(message):
        action = "add"
    else:
        return None

    for token in _TOKEN_RE.findall(message):
        upper = token.upper()
        if upper not in _WATCHLIST_STOPWORDS:
            return LLMWatchlistChange(ticker=upper, action=action)
    return None


def build_mock_response(message: str, context: PortfolioContext) -> LLMChatResponse:
    trade = _extract_trade(message)
    if trade is not None:
        quantity_text = f"{trade.quantity:g}"
        return LLMChatResponse(
            message=f"I'll {trade.side} {quantity_text} {trade.ticker}.",
            trades=[trade],
            watchlist_changes=[],
        )

    watchlist_change = _extract_watchlist_change(message)
    if watchlist_change is not None:
        if watchlist_change.action == "add":
            reply = f"I'll add {watchlist_change.ticker} to your watchlist."
        else:
            reply = f"I'll remove {watchlist_change.ticker} from your watchlist."
        return LLMChatResponse(message=reply, trades=[], watchlist_changes=[watchlist_change])

    position_count = len(context.positions)
    reply = (
        f"You have ${context.cash_balance:,.2f} in cash and {position_count} open "
        f"position{'s' if position_count != 1 else ''}, for a total portfolio value "
        f"of ${context.total_value:,.2f}."
    )
    return LLMChatResponse(message=reply, trades=[], watchlist_changes=[])


def build_mock_raw_response(message: str, context: PortfolioContext) -> str:
    """Serialized the same way a real model's structured output would be,
    so it exercises the identical `parse_llm_response` path."""
    return build_mock_response(message, context).model_dump_json()
