"""app.llm.config: is_mock_mode/has_api_key re-read the environment on
every call (B11), and the startup warning fires only when genuinely
unconfigured.
"""

from __future__ import annotations

import logging

from app.llm import config


def test_has_api_key_true_when_set(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-something")
    assert config.has_api_key() is True


def test_has_api_key_false_when_blank_or_missing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
    assert config.has_api_key() is False
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert config.has_api_key() is False


def test_is_mock_mode_true_only_for_exact_string_true(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    assert config.is_mock_mode() is True
    monkeypatch.setenv("LLM_MOCK", "TRUE")
    assert config.is_mock_mode() is True
    monkeypatch.setenv("LLM_MOCK", "false")
    assert config.is_mock_mode() is False
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert config.is_mock_mode() is False


def test_warns_when_unconfigured(monkeypatch, caplog):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="app.llm.config"):
        config._warn_if_unconfigured()
    assert any("OPENROUTER_API_KEY is not set" in r.message for r in caplog.records)


def test_no_warning_when_mock_mode_enabled(monkeypatch, caplog):
    monkeypatch.setenv("LLM_MOCK", "true")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="app.llm.config"):
        config._warn_if_unconfigured()
    assert caplog.records == []


def test_no_warning_when_api_key_present(monkeypatch, caplog):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-something")
    with caplog.at_level(logging.WARNING, logger="app.llm.config"):
        config._warn_if_unconfigured()
    assert caplog.records == []
