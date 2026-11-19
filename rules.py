"""Shared, versioned instructions and validation for every agent runtime."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
DOCUMENTS = ("AGENTS.md", "RULES.md", "WORKFLOW.md", "ORCHESTRATOR.md", "RUNNERS.md", "README.md")
INTERVAL = 3


def packet():
    contents = "\n\n".join(f"# {name}\n{(ROOT/name).read_text(encoding='utf-8')}" for name in DOCUMENTS)
    return {"sha256": hashlib.sha256(contents.encode()).hexdigest(), "text": contents}


def check_observation(path, job, target_digest):
    evidence = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    expected_va = 0x400000 + job["rva"]  # Pinned Steam PE32 preferred image base.
    if not isinstance(evidence, dict):
        raise ValueError("expected one REA Evidence object")
    try:
        observation = evidence["normalized_result"]
        procedure = observation["procedure"]
        body = procedure["body"]
        ranges = body["ranges"]
        valid = (evidence["subject"]["digest"]["sha256"] == target_digest
                 and evidence["operation"] == "read_function_instructions"
                 and bool(observation["instructions"])
                 and int(str(procedure["address"]), 0) == expected_va
                 and len(ranges) == 1 and int(ranges[0]["start"],0) == expected_va
                 and int(ranges[0]["end"],0) == expected_va + job["size"] - 1
                 and re.fullmatch(r"ev_[0-9a-f]{64}", evidence["evidence_id"]))
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("REA instruction evidence must identify the pinned target and leased entry")
    return evidence["evidence_id"]


def replay_observation(target, job, target_digest, saved, output):
    """Run the pinned REA CLI independently before trusting a worker observation."""
    node = shutil.which("node")
    npx = shutil.which("npx")
    if not node or not npx:
        raise ValueError("REA replay requires Node.js and npx")
    launcher = Path(node).with_name("node_modules") / "npm/bin/npx-cli.js"
    argv = [node, str(launcher)] if launcher.is_file() else [npx]
    argv += ["-y", "rea-agents@6.8.0", "instructions", str(target),
             hex(0x400000 + job["rva"]), "--format", "json"]
    with Path(output).open("wb") as stream:
        subprocess.run(argv, stdout=stream, timeout=600, check=True)
    check_observation(output, job, target_digest)
    def instructions(path):
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))["normalized_result"]["instructions"]
    if instructions(saved) != instructions(output):
        raise ValueError("independent REA replay differs from worker's instruction listing")
