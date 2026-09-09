"""Pydantic request bodies. Response shapes are plain dicts (see the
`*_view` / `to_dict()` helpers in app.api routers) so this file only needs
to cover inbound validation -- see planning/API_CONTRACT.md for the exact
response JSON every endpoint returns.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    quantity: float
    side: Literal["buy", "sell"]


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
