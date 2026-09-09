"""Structured output schema for the LLM chat turn (PLAN §9).

`LLMChatResponse` is the model's raw structured output -- NOT the
`POST /api/chat` response shape. See `planning/LLM_DESIGN.md` §1: the API
response's `trades_executed`/`trades_failed`/`watchlist_changes` blocks
are built by `app.llm.executor` from this after each action is run through
the real validated paths (§13.A3 -- the model cannot know outcomes when it
writes `message`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMTrade(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class LLMWatchlistChange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticker: str
    action: Literal["add", "remove"]


class LLMChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    trades: list[LLMTrade] = Field(default_factory=list)
    watchlist_changes: list[LLMWatchlistChange] = Field(default_factory=list)
