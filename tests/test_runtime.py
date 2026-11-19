import json
import multiprocessing
import os

import pytest

from asof.runtime import WorkerJob, peak_rss_bytes, write_receipt


def test_receipts_are_strict_and_never_overwrite_an_attempt(tmp_path):
    path = tmp_path / "receipt.json"
    with pytest.raises(ValueError):
        write_receipt(path, {"bad": float("nan")})
    assert not path.exists()
    write_receipt(path, {"status": "invented"})
    assert json.loads(path.read_text()) == {"status": "invented"}
    with pytest.raises(FileExistsError):
        write_receipt(path, {"status": "replacement"})
    assert json.loads(path.read_text()) == {"status": "invented"}


def blocked_worker(ready, gate):
    ready.set()
    gate.wait()


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-process Job")
def test_packaged_job_pins_and_terminates_only_the_owned_gated_child():
    context = multiprocessing.get_context("spawn")
    ready, gate = context.Event(), context.Event()
    process = context.Process(target=blocked_worker, args=(ready, gate))
    job = WorkerJob(memory_bytes=512 << 20)
    process.start()
    try:
        assert process.pid is not None
        mask = job.attach(process.pid)
        assert mask.bit_count() == 1
        assert job.pin(process.pid, mask) == mask
        assert ready.wait(timeout=10) and process.is_alive()
        job.close()
        process.join(timeout=10)
        assert not process.is_alive() and not gate.is_set()
        assert peak_rss_bytes() > 0
    finally:
        job.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        process.close()


def test_invalid_resource_limit_refuses_before_platform_api():
    with pytest.raises(ValueError, match="positive byte"):
        WorkerJob(memory_bytes=0)
