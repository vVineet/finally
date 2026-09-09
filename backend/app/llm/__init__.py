"""LLM chat integration (PLAN §9, §13). See planning/LLM_DESIGN.md for the
full design (system prompt, structured output schema, context/history
budget, mock catalogue) and planning/API_CONTRACT.md for the frozen
`POST /api/chat` request/response contract this package implements.

Public API (import from here, not submodules):
    is_mock_mode, has_api_key           - app.llm.config
    build_portfolio_context             - app.llm.context
    build_messages                      - app.llm.prompts
    call_llm, LLMCallError              - app.llm.client
    build_mock_raw_response             - app.llm.mock
    parse_llm_response, LLMParseError   - app.llm.parser
    LLMChatResponse, LLMTrade, LLMWatchlistChange  - app.llm.schema
    execute_trades, execute_watchlist_changes      - app.llm.executor
"""

from .client import LLMCallError, call_llm
from .config import has_api_key, is_mock_mode
from .context import PortfolioContext, build_portfolio_context
from .executor import execute_trades, execute_watchlist_changes
from .mock import build_mock_raw_response
from .parser import LLMParseError, parse_llm_response
from .prompts import build_messages
from .schema import LLMChatResponse, LLMTrade, LLMWatchlistChange

__all__ = [
    "is_mock_mode",
    "has_api_key",
    "PortfolioContext",
    "build_portfolio_context",
    "build_messages",
    "call_llm",
    "LLMCallError",
    "build_mock_raw_response",
    "parse_llm_response",
    "LLMParseError",
    "LLMChatResponse",
    "LLMTrade",
    "LLMWatchlistChange",
    "execute_trades",
    "execute_watchlist_changes",
]
