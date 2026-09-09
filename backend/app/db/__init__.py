"""Database layer for FinAlly.

See planning/DATABASE_DESIGN.md for the full contract. Public API:

    DEFAULT_USER_ID     - "default", the single-user id used everywhere

    Domain models: UserProfile, WatchlistItem, Position, Trade,
    PortfolioSnapshot, ChatMessage, TradeResult

    Errors: DBError, InvalidTradeError, InsufficientCashError,
    InsufficientSharesError

    Repository (all async, dispatched to a threadpool internally):
        init_db, get_user_profile, get_cash_balance,
        get_watchlist, add_to_watchlist, remove_from_watchlist,
        get_positions, get_position,
        execute_trade, get_trades,
        record_snapshot, get_snapshots,
        add_chat_message, get_chat_history,
        reset_portfolio
"""

from .connection import DEFAULT_USER_ID, get_db_path
from .errors import DBError, InsufficientCashError, InsufficientSharesError, InvalidTradeError
from .models import (
    ChatMessage,
    PortfolioSnapshot,
    Position,
    Trade,
    TradeResult,
    UserProfile,
    WatchlistItem,
)
from .repository import (
    add_chat_message,
    add_to_watchlist,
    execute_trade,
    get_cash_balance,
    get_chat_history,
    get_position,
    get_positions,
    get_snapshots,
    get_trades,
    get_user_profile,
    get_watchlist,
    init_db,
    record_snapshot,
    remove_from_watchlist,
    reset_portfolio,
)

__all__ = [
    "DEFAULT_USER_ID",
    "get_db_path",
    "DBError",
    "InvalidTradeError",
    "InsufficientCashError",
    "InsufficientSharesError",
    "UserProfile",
    "WatchlistItem",
    "Position",
    "Trade",
    "PortfolioSnapshot",
    "ChatMessage",
    "TradeResult",
    "init_db",
    "get_user_profile",
    "get_cash_balance",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_positions",
    "get_position",
    "execute_trade",
    "get_trades",
    "record_snapshot",
    "get_snapshots",
    "add_chat_message",
    "get_chat_history",
    "reset_portfolio",
]
