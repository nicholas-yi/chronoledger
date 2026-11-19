import builtins
import json
import socket

import pytest

from asof import cli, ledger
from asof.demo import demo


def test_demo_is_an_invented_end_to_end_command_without_client_file_or_trial_io(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("dataset-free demo attempted I/O")

    # Imports happen before the tripwires; this is not an OS sandbox.
    from asof.research.identification import OutcomeBound
    from asof.research.trajectories import signature2

    assert OutcomeBound and signature2
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(cli, "EdgarClient", forbidden)
    monkeypatch.setattr(ledger, "log_trial", forbidden)
    cli.main(["demo"])
    result = json.loads(capsys.readouterr().out)
    assert result == json.loads(json.dumps(demo()))
    assert result["evidence_kind"] == "invented_fixture_not_market_evidence"
    assert result["accounting"]["status"] == "consistent"
    assert result["order"]["same_endpoint"] and result["order"]["first_area"] == -0.5
    assert result["identification"]["unknown_short_lower_bound"] == "-infinity"
