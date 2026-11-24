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


@pytest.mark.parametrize(("claim", "verdict"), [
    ("FictionPoppy reported revenue of 18 USD million for 2017.", "supported"),
    ("FictionPoppy reported revenue of 19 USD million for 2017.", "contradicted"),
    ("FictionPoppy beat expectations.", "review"),
])
def test_check_claim_decides_from_the_source_file_alone(tmp_path, capsys, claim, verdict):
    source = tmp_path / "source.txt"
    source.write_text("FictionPoppy reported revenue\u200b of 18 USD million for 2017.", encoding="utf-8")
    cli.main(["check-claim", str(source), claim])
    result = json.loads(capsys.readouterr().out)
    assert result["verdict"] == verdict
    assert result["decision_origin"] == "source_rules_not_model"
    assert result["source_normalization"] == {"invisible_format_removed": 1}
