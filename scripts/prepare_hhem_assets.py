"""Download only pinned public HHEM weights/config/tokenizer; inspect code before any execution."""

import hashlib
import json
import urllib.request
from pathlib import Path

from asof.runtime import write_receipt

REPOSITORIES = (
    ("vectara/hallucination_evaluation_model", "de9a5e6ba9ba49531a022dba17e35ffeb2a6fad8", "hhem",
     ("config.json", "configuration_hhem_v2.py", "modeling_hhem_v2.py", "model.safetensors")),
    ("google/flan-t5-base", "7bcac572ce56db69c1ea7c8af255c5d7c9672fc2", "foundation",
     ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "spiece.model")),
)


def main():
    root = Path(__file__).resolve().parents[1]
    private = root / "data" / "hhem_assets_v1"
    receipt = root / "results" / "hhem_assets.json"
    if receipt.exists():
        raise FileExistsError("asset receipt exists; verify pins rather than overwrite")
    private.mkdir(parents=True, exist_ok=True)
    rows = []
    for repo, revision, directory, names in REPOSITORIES:
        with urllib.request.urlopen(
                f"https://huggingface.co/api/models/{repo}/tree/{revision}", timeout=30) as response:
            tree = {row["path"]: row for row in json.load(response)}
        for name in names:
            info = tree[name]
            size = info["size"]
            if size > 450 << 20:
                raise ValueError("unexpected public artifact size")
            path = private / directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
            if not path.exists():
                with urllib.request.urlopen(url, timeout=60) as response, path.open("xb") as stream:
                    total = 0
                    while chunk := response.read(1 << 20):
                        total += len(chunk)
                        if total > size:
                            raise ValueError("artifact exceeds pinned size")
                        stream.write(chunk)
            raw_hash = hashlib.sha256()
            git_hash = hashlib.sha1(f"blob {size}\0".encode(), usedforsecurity=False)
            count = 0
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    count += len(chunk)
                    raw_hash.update(chunk)
                    git_hash.update(chunk)
            if count != size:
                raise ValueError("incomplete artifact; do not use partial bytes")
            if "lfs" in info:
                if raw_hash.hexdigest() != info["lfs"]["oid"]:
                    raise ValueError("LFS public SHA256 mismatch")
            elif git_hash.hexdigest() != info["oid"]:
                raise ValueError("public Git blob pin mismatch")
            rows.append({"repo": repo, "revision": revision, "relative_path": f"{directory}/{name}",
                         "size": size, "sha256": raw_hash.hexdigest()})
            print(f"Verified public artifact {directory}/{name} ({size} bytes)", flush=True)
    write_receipt(receipt, {
        "status": "pinned_public_artifacts_downloaded_not_inference",
        "model": REPOSITORIES[0][0], "model_revision": REPOSITORIES[0][1],
        "foundation_revision": REPOSITORIES[1][1], "artifacts": rows,
        "private_location": "data/hhem_assets_v1", "model_calls": 0,
        "custom_code_review": "Inspected two small pinned modules before execution. Standard Torch/Transformers imports; constructor loads foundation config/tokenizer. Override foundation to pinned local path and force offline before loading.",
        "license": "HHEM and foundation model cards declare Apache-2.0; weights are not added to Git.",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
