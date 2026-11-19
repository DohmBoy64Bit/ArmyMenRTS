"""Publish immutable text copies of source and evidence beside a progress snapshot."""

import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


def publish_proof(report, public_dir):
    repo = Path(__file__).resolve().parent
    for function in report["functions"]:
        if function["status"] != "matched":
            continue
        revision = function["revision"]
        if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise ValueError("Expected a full Git revision in the verified record")
        for field in ("source", "evidence"):
            path = PurePosixPath(function[field])
            if path.is_absolute() or not path.parts or ".." in path.parts:
                raise ValueError(f"Invalid public reconstruction path: {path}")
            content = subprocess.check_output(
                ["git", "cat-file", "blob", f"{revision}:{path}"], cwd=repo
            )
            content.decode("utf-8")
            if b"\x00" in content:
                raise ValueError("Expected text source or evidence")
            relative = f"proof/{revision}/{function['rva']:08x}/{field}.txt"
            dest = Path(public_dir) / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as temp:
                temp.write(content)
            os.replace(temp.name, dest)
            function["public_" + field] = relative
