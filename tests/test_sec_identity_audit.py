import importlib.util
from pathlib import Path

import httpx
import pytest


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("sec_identity_audit", scripts / "sec_identity_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_consideration_is_only_a_scoped_text_hint_not_a_terminal_payoff(monkeypatch) -> None:
    script = _script(monkeypatch)
    result = script.text_oracle(
        "Item 2.01 Completion. The cash consideration was paid subject to elections. "
        "Item 9.01 Other exhibits include shares of common stock.", "cash_acquisition")
    assert result["consideration"] == "cash_terms_candidate"
    assert result["oracle_status"] == "partial_text_support"
    assert len(result["evidence"]) == 1
    assert script.text_oracle("No Item section is here", "cash_acquisition")[
        "oracle_status"] == "unresolved"
    with pytest.raises(ValueError, match="empty"):
        script.text_oracle("", "continuing")


def test_actual_request_hook_stops_before_exceeding_budget_without_network(monkeypatch) -> None:
    script = _script(monkeypatch)
    monkeypatch.setenv("ASOF_USER_AGENT", "Synthetic Test test@example.com")
    monkeypatch.setattr(script, "MAX_REQUESTS", 2)
    monkeypatch.setattr(script.BudgetClient, "_throttle", lambda self: None)
    client = script.BudgetClient()
    try:
        request = httpx.Request("GET", "https://www.sec.gov/synthetic-not-requested")
        client._count_request(request)
        client._count_request(request)
        with pytest.raises(script.RequestBudgetExceeded):
            client._count_request(request)
        assert client.http_attempts == 2
    finally:
        client.close()
