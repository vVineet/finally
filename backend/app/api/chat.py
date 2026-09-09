"""Chat endpoints: GET /api/chat/history (implemented), POST /api/chat
(contract defined, handler stubbed for the LLM Engineer).

See planning/API_CONTRACT.md "POST /api/chat" for the full target request/
response contract this handler must eventually satisfy, including how it
should call `app.db.add_chat_message`, execute trades/watchlist changes via
the same validated paths `app/api/portfolio.py` and `app/api/watchlist.py`
use, and return updated portfolio/watchlist state per §13.C2.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.db import get_chat_history

from .schemas import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])

DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 200


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


@router.post("")
async def chat(body: ChatRequest) -> dict:
    """STUB. Registered so the route/contract exists for the frontend to
    build against; the LLM Engineer owns the implementation (portfolio
    context loading, LiteLLM/OpenRouter call, structured-output parsing,
    trade/watchlist auto-execution, and persistence via
    app.db.add_chat_message). Currently always returns 501.
    """
    raise HTTPException(
        status_code=501,
        detail="Chat is not yet implemented. See planning/API_CONTRACT.md for the target contract.",
    )
