"""Parser must degrade gracefully on malformed/partial/adversarial LLM
output: either a valid LLMChatResponse, or LLMParseError -- never an
unhandled exception, per PLAN §13's "graceful degradation" requirement.
"""

from __future__ import annotations

import json

import pytest

from app.llm.parser import LLMParseError, parse_llm_response
from app.llm.schema import LLMChatResponse


def test_parses_a_well_formed_response():
    raw = json.dumps(
        {
            "message": "I'll buy 10 AAPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
        }
    )
    result = parse_llm_response(raw)
    assert isinstance(result, LLMChatResponse)
    assert result.message == "I'll buy 10 AAPL."
    assert len(result.trades) == 1
    assert result.trades[0].ticker == "AAPL"


def test_parses_response_with_no_trades_or_watchlist_changes_keys():
    raw = json.dumps({"message": "Your portfolio looks balanced."})
    result = parse_llm_response(raw)
    assert result.message == "Your portfolio looks balanced."
    assert result.trades == []
    assert result.watchlist_changes == []


def test_ignores_unknown_extra_top_level_keys():
    raw = json.dumps({"message": "hi", "confidence": 0.97, "reasoning": "because"})
    result = parse_llm_response(raw)
    assert result.message == "hi"


def test_strips_json_code_fence():
    raw = '```json\n{"message": "fenced reply", "trades": [], "watchlist_changes": []}\n```'
    result = parse_llm_response(raw)
    assert result.message == "fenced reply"


def test_strips_plain_code_fence_without_language_tag():
    raw = '```\n{"message": "fenced"}\n```'
    result = parse_llm_response(raw)
    assert result.message == "fenced"


def test_empty_string_raises_parse_error():
    with pytest.raises(LLMParseError):
        parse_llm_response("")


def test_plain_prose_not_json_raises_parse_error():
    with pytest.raises(LLMParseError):
        parse_llm_response("Sure, I'll buy 10 AAPL for you right away!")


def test_truncated_json_raises_parse_error():
    with pytest.raises(LLMParseError):
        parse_llm_response('{"message": "I\'ll buy 10 AAPL", "trades": [{"ticker": "AAPL"')


def test_json_array_instead_of_object_raises_parse_error():
    with pytest.raises(LLMParseError):
        parse_llm_response('["message", "not an object"]')


def test_object_missing_message_raises_parse_error():
    raw = json.dumps({"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]})
    with pytest.raises(LLMParseError):
        parse_llm_response(raw)


def test_message_as_non_string_raises_parse_error():
    raw = json.dumps({"message": 12345})
    with pytest.raises(LLMParseError):
        parse_llm_response(raw)


def test_blank_message_raises_parse_error():
    raw = json.dumps({"message": "   "})
    with pytest.raises(LLMParseError):
        parse_llm_response(raw)


def test_invalid_trade_side_salvages_message_and_drops_trades():
    raw = json.dumps(
        {
            "message": "I'll hold your position.",
            "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 10}],
            "watchlist_changes": [],
        }
    )
    result = parse_llm_response(raw)
    assert result.message == "I'll hold your position."
    assert result.trades == []


def test_trade_quantity_as_string_salvages_message_and_drops_trades():
    raw = json.dumps(
        {
            "message": "I'll buy some AAPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": "ten"}],
        }
    )
    result = parse_llm_response(raw)
    assert result.message == "I'll buy some AAPL."
    assert result.trades == []


def test_trades_as_non_list_salvages_message_and_drops_trades():
    raw = json.dumps({"message": "hmm", "trades": "AAPL"})
    result = parse_llm_response(raw)
    assert result.message == "hmm"
    assert result.trades == []


def test_invalid_watchlist_action_salvages_message_and_drops_watchlist_changes():
    raw = json.dumps(
        {
            "message": "I'll take a look.",
            "watchlist_changes": [{"ticker": "PYPL", "action": "star"}],
        }
    )
    result = parse_llm_response(raw)
    assert result.message == "I'll take a look."
    assert result.watchlist_changes == []


def test_message_with_embedded_quotes_and_newlines_and_unicode():
    raw = json.dumps({"message": 'He said "buy\nAAPL" — 10% up today 📈'})
    result = parse_llm_response(raw)
    assert "AAPL" in result.message
    assert "📈" in result.message


def test_adversarial_huge_trades_array_does_not_crash():
    trades = [{"ticker": "AAPL", "side": "buy", "quantity": 1} for _ in range(5000)]
    raw = json.dumps({"message": "buying a lot", "trades": trades})
    result = parse_llm_response(raw)
    assert len(result.trades) == 5000


def test_adversarial_deeply_nested_extra_field_does_not_crash():
    nested: dict = {"a": 1}
    for _ in range(200):
        nested = {"nested": nested}
    raw = json.dumps({"message": "ok", "extra_field": nested})
    result = parse_llm_response(raw)
    assert result.message == "ok"


def test_non_utf8_safe_garbage_raises_parse_error_not_exception():
    with pytest.raises(LLMParseError):
        parse_llm_response("\x00\x01\x02 not json at all {{{")
