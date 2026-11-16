"""Freeze a future answer-first server policy or explicitly launch its owned server."""

import argparse
import json
from pathlib import Path

from asof import ledger
from asof.local_model_runtime import RuntimePolicy, launch_owned_server, verify_supported_package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "serve"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--prompt-cache-MiB", type=int, default=0)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    package = verify_supported_package(args.executable)
    if args.phase == "freeze":
        if args.config.exists():
            raise RuntimeError("runtime_config_exists")
        args.config.write_text(json.dumps({"policy":RuntimePolicy(args.prompt_cache_MiB).manifest(),
            "executable_SHA256":ledger.file_sha256(args.executable),
            "package":package,
            "authorization":"Futureconfigurationonly;not permission tolaunch server or inference."
            },indent=2),encoding="utf-8")
    else:
        if args.log is None or args.receipt is None:
            parser.error("--log and --receipt required for explicit owned-server launch")
        if ledger.lineage()["git_dirty"]:
            raise RuntimeError("commit_frozen_runtime_config_before_launch")
        config = json.loads(args.config.read_bytes())
        if ledger.file_sha256(args.executable) != config["executable_SHA256"]:
            raise ValueError("pinned_Ollama_executable_changed")
        if package != config["package"]:
            raise ValueError("pinned_runtime_support_changed")
        policy = RuntimePolicy(config["policy"]["prompt_cache_MiB"])
        if policy.manifest() != config["policy"]:
            raise ValueError("runtime_policy_changed")
        process = launch_owned_server(args.executable,args.log,args.receipt,policy)
        print(json.dumps({"owned_server_PID":process.pid,"host":"127.0.0.1:11435"}))


if __name__ == "__main__":
    main()
