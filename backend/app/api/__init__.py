"""REST API routers. See planning/API_CONTRACT.md for the full contract.

`app.main` includes each of these routers plus `app.market.create_stream_router`.
"""

from . import chat, health, portfolio, trades, watchlist
from .errors import register_exception_handlers

__all__ = ["chat", "health", "portfolio", "trades", "watchlist", "register_exception_handlers"]
