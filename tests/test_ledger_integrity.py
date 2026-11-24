import hashlib
import multiprocessing
import subprocess

import pytest

from asof import ledger


def append_fixture(path, index) -> None:
    ledger.log_trial("SYNTHETIC", {"index": index}, "development", {"n": 1}, path)


def test_legacy_prefix_is_preserved_and_chain_detects_mutation(tmp_path) -> None:
    path = tmp_path / "invented.jsonl"
    prefix = b'{"hypothesis":"OLD","period":"development","config_hash":"old"}\r\n'
    path.write_bytes(prefix)
    anchor = ledger.LedgerAnchor(len(prefix), 1, hashlib.sha256(prefix).hexdigest())
    ledger.log_trial("NEW", {"x": 1}, "development", {}, path, anchor=anchor)
    assert path.read_bytes().startswith(prefix)
    checked = ledger.verify_chain(path, anchor=anchor)
    assert (checked.legacy_rows, checked.chained_rows) == (1, 1)
    entry = ledger.read_ledger(path, anchor=anchor)[1]
    assert entry["previous_hash"] == anchor.sha256
    path.write_bytes(path.read_bytes().replace(b'"x": 1', b'"x": 2'))
    with pytest.raises(ledger.LedgerIntegrityError, match="chain"):
        ledger.verify_chain(path, anchor=anchor)
    with pytest.raises(ledger.LedgerIntegrityError):
        ledger.log_trial("NEW", {}, "development", {}, path, anchor=anchor)


def test_anchor_allows_only_checkout_line_ending_equivalence(tmp_path) -> None:
    path = tmp_path / "invented.jsonl"
    prefix = b'{"hypothesis":"OLD"}\r\n'
    anchor = ledger.LedgerAnchor(len(prefix), 1, hashlib.sha256(prefix).hexdigest())
    path.write_bytes(prefix.replace(b"\r\n", b"\n"))
    ledger.log_trial("NEW", {}, "development", {}, path, anchor=anchor)
    assert ledger.verify_chain(path, anchor=anchor).chained_rows == 1
    path.write_bytes(path.read_bytes().replace(b'OLD', b'BAD'))
    with pytest.raises(ledger.LedgerIntegrityError, match="prefix"):
        ledger.verify_chain(path, anchor=anchor)


def test_missing_inputs_and_same_basename_sources_have_explicit_distinct_keys(tmp_path) -> None:
    a, b = tmp_path / "a" / "input.txt", tmp_path / "b" / "input.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_text("invented a")
    b.write_text("invented b")
    missing = tmp_path / "missing.txt"
    result = ledger.lineage([a, b, missing])
    assert result["inputs"][ledger.input_key(a)] != result["inputs"][ledger.input_key(b)]
    assert result["inputs"][ledger.input_key(missing)] is None
    assert ledger.input_key(missing) in result["missing_inputs"]


def test_dirty_check_includes_protocol_changes_but_not_ignored_files(tmp_path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored/\n")
    (tmp_path / "protocol.json").write_text("{}")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.test", "commit", "-qm", "invented"], check=True)
    monkeypatch.setattr(ledger, "PROJECT_ROOT", tmp_path)
    assert ledger.lineage()["git_dirty"] is False
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "fixture").write_text("ignored")
    assert ledger.lineage()["git_dirty"] is False
    (tmp_path / "protocol.json").write_text('{"changed":true}')
    assert ledger.lineage()["git_dirty"] is True


def test_exclusive_appends_form_one_valid_chain_across_workers(tmp_path) -> None:
    path = tmp_path / "concurrent.jsonl"
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=append_fixture, args=(path, i)) for i in range(3)]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
            process.close()
    checked = ledger.verify_chain(path)
    assert checked.chained_rows == 3
    assert len({r["config"]["index"] for r in ledger.read_ledger(path)}) == 3


def test_truncated_tail_is_not_silently_repaired(tmp_path) -> None:
    path = tmp_path / "truncated.jsonl"
    ledger.log_trial("SYNTHETIC", {}, "development", {}, path)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ledger.LedgerIntegrityError, match="incomplete"):
        ledger.verify_chain(path)


def test_committed_ledger_history_is_append_only() -> None:
    assert ledger.verify_committed_history() >= 2


def test_deleting_a_committed_tail_row_is_detected(tmp_path) -> None:
    import subprocess

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", *args],
                       cwd=tmp_path, check=True, capture_output=True)

    path = tmp_path / "ledger.jsonl"
    git("init", "-q")
    path.write_text('{"row": 1}\n{"row": 2}\n')
    git("add", "ledger.jsonl")
    git("commit", "-q", "-m", "two rows")
    path.write_text('{"row": 1}\n')  # the hash chain alone accepts a valid shorter prefix
    with pytest.raises(ledger.LedgerIntegrityError, match="working tree"):
        ledger.verify_committed_history(path, root=tmp_path)
