"""call_llm wraps every failure mode in LLMCallError (network, timeout,
empty content, malformed provider response) -- never lets a raw exception
from litellm reach the route handler. Uses monkeypatch, no real network
call (real-network verification was done manually, see LLM_SUMMARY.md).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.llm.client as client_module
from app.llm.client import LLMCallError, call_llm


def _fake_completion_returning(content: str):
    def _fake(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return _fake


def test_call_llm_returns_content_on_success(monkeypatch):
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning('{"message": "hi"}'))
    result = call_llm([{"role": "user", "content": "hello"}])
    assert result == '{"message": "hi"}'


def test_call_llm_wraps_network_exception(monkeypatch):
    def _raise(**kwargs):
        raise ConnectionError("boom")

    monkeypatch.setattr(client_module, "completion", _raise)
    with pytest.raises(LLMCallError):
        call_llm([{"role": "user", "content": "hello"}])


def test_call_llm_wraps_empty_content(monkeypatch):
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning(""))
    with pytest.raises(LLMCallError):
        call_llm([{"role": "user", "content": "hello"}])


def test_call_llm_wraps_missing_choices(monkeypatch):
    def _fake(**kwargs):
        return SimpleNamespace(choices=[])

    monkeypatch.setattr(client_module, "completion", _fake)
    with pytest.raises(LLMCallError):
        call_llm([{"role": "user", "content": "hello"}])
