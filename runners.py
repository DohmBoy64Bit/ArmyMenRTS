"""Dispatch leased reconstruction jobs to isolated CLI agent checkouts."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
import uuid
import rules


ROOT = Path(__file__).resolve().parent
INSTRUCTIONS = "Read worker-job.json in this checkout and carry out its instructions."
RUNNERS = {"pi", "codex", "opencode", "api"}


def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f"Install {name} or select another runner.")
    return path


def launcher(runner):
    name = "pi" if runner == "api" else runner
    if os.name != "nt":
        return [executable(name)]
    if path := shutil.which(name + ".exe"):
        return [path]
    # Use argv directly. The Windows shims pass arguments through cmd.exe.
    directory = Path(executable(name + ".cmd")).parent
    if name == "pi":
        for js in (directory / "pi-launcher.js",
                   directory / "node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
                   directory / "node_modules/@mariozechner/pi-coding-agent/dist/cli.js"):
            if js.is_file():
                return [executable("node"), str(js)]
    if name == "opencode":
        binary = directory / "node_modules/opencode-ai/bin/opencode.exe"
        if binary.is_file():
            return [str(binary)]
        script = binary.with_suffix("")
        if script.is_file():
            return [executable("node"), str(script)]
    raise ValueError(f"Cannot resolve the native executable or node entry point for {name}.")


def configuration(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("version") != 1 or not isinstance(config.get("slots"), list):
        raise ValueError("Expected version 1 and a slots array.")
    if not 1 <= len(config["slots"]) <= 10:
        raise ValueError("Configure one to ten worker slots.")
    slots = []
    for override in config["slots"]:
        slot = {"runner": "codex", "timeout_seconds": 1800,
                **config.get("defaults", {}), **override}
        runner = slot["runner"]
        if runner not in RUNNERS:
            raise ValueError(f"Unknown worker runner {runner}")
        if type(slot["timeout_seconds"]) is not int or slot["timeout_seconds"] <= 0:
            raise ValueError("timeout_seconds must be a positive integer.")
        allowed = {"runner", "timeout_seconds", "model", "provider"}
        if runner == "api":
            allowed.update({"endpoint", "key_env"})
            endpoint = urlparse(slot.get("endpoint", ""))
            if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
                raise ValueError("An API slot requires an HTTP(S) endpoint.")
            if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
                raise ValueError("Use key_env for endpoint credentials.")
            key = slot.get("key_env")
            if key and (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not os.getenv(key)):
                raise ValueError(f"Missing or invalid API credential environment variable {key!r}")
        if (runner == "api" or slot.get("provider")) and not slot.get("model"):
            raise ValueError("Choose a model when overriding the provider or endpoint.")
        if set(slot) - allowed:
            raise ValueError(f"Unsupported {runner} options: {sorted(set(slot) - allowed)}")
        slot["launcher"] = launcher(runner)
        slots.append(slot)
    return slots


def command(slot, attempt):
    args = slot["launcher"].copy()
    env = os.environ.copy()
    runner, provider, model = slot["runner"], slot.get("provider"), slot.get("model")
    if runner == "api":
        provider = provider or "reconstruction"
        settings = attempt / "pi"
        settings.mkdir()
        env["PI_CODING_AGENT_DIR"] = str(settings)
        key = "$" + slot["key_env"] if slot.get("key_env") else "local"
        config = {"baseUrl": slot["endpoint"], "api": "openai-completions",
                  "apiKey": key, "models": [{"id": model}]}
        (settings / "models.json").write_text(json.dumps({"providers": {provider: config}}), encoding="utf-8")
    if runner in {"pi", "api"}:
        args.extend(["--print", "--no-session"])
        if provider:
            args.extend(["--provider", provider])
    elif runner == "codex":
        args.extend(["exec", "--sandbox", "workspace-write"])
        if provider:
            args.extend(["-c", "model_provider=" + json.dumps(provider)])
    else:
        args.append("run")
        if provider:
            model = f"{provider}/{model}"
    if model:
        args.extend(["--model", model])
    return [*args, INSTRUCTIONS], env


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run_job(db, job, slot, attempt, stop):
    import workflow

    revision = job["base_revision"]
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision):
        raise ValueError("Enqueue a job against an immutable Git commit.")
    checkout = attempt / "tree"
    git(ROOT, "worktree", "add", "--detach", str(checkout), revision)
    address = f"{job['rva']:08x}"
    directory = f"reconstruction/{address}"
    build, manifest = f"{directory}/build.py", f"{directory}/function.json"
    instructions = (
        f"Use your own REA session or a process-local REA CLI. CLI fallback: npx -y rea-agents@6.8.0 "
        f"instructions TARGET VA --format json, where VA is the PE image base plus the leased RVA. "
        f"Inspect the pinned Steam executable "
        f"from WORKFLOW.md. Reconstruct the assigned function from evidence. Read the repository "
        f"README and existing examples. Write committed files only within {directory}/. Include C or C++ source, "
        f"an evidence markdown file describing the reference, boundary, caller and build experiment, "
        f"{build} accepting --output PATH and writing raw compiled function bytes, and {manifest} "
        f"with rva and size integers, name, source and evidence (repo-relative paths). Test the build. "
        f"Do not copy reference bytes into the build or submit a guessed match. Do not change Git "
        f"history, run the dispatcher, or edit the baseline. If blocked, describe why in your final "
        f"response. The orchestrator records the patch and independently verifies matches."
    )
    current_rules = rules.packet()
    instructions = ("Read the entire rules_packet.text before starting. Its current rules apply even "
                    "when the base checkout contains older instructions. Open the target with REA and "
                    "call read_function_instructions for this entry VA. Save its full Evidence object to "
                    "rea-observation.json in the checkout root. Cite that evidence ID and explain the "
                    "specific finding in the evidence Markdown. Set rules_sha256 in function.json to "
                    "rules_packet.sha256 after reading. " + instructions)
    assignment = {"version": 2, "rules_packet": current_rules, "job": dict(job), "target": str(workflow.TARGET),
                  "sha256": workflow.DIGEST, "instructions": instructions}
    (checkout / "worker-job.json").write_text(json.dumps(assignment, indent=2), encoding="utf-8")
    argv, env = command(slot, attempt)
    log = attempt / "worker.log"
    deadline = time.monotonic() + slot["timeout_seconds"]
    with log.open("wb") as output:
        process = subprocess.Popen(argv, cwd=checkout, env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
        try:
            while process.poll() is None:
                if stop.is_set():
                    raise ValueError("Dispatch interrupted")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Worker timed out")
                workflow.renew(db, job)
                try:
                    process.wait(timeout=min(5, max(0.1, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode != 0:
                raise ValueError(f"Runner exited with status {process.returncode}. See {log}.")
        finally:
            stop_process(process)
    if git(checkout, "rev-parse", "HEAD") != revision:
        raise ValueError("Worker changed its base commit.")
    record = json.loads((checkout / manifest).read_text(encoding="utf-8"))
    if (record.get("rva"), record.get("size")) != (job["rva"], job["size"]):
        raise ValueError("Worker manifest does not cover its leased range.")
    scope = (checkout / directory).resolve()
    observation = checkout / "rea-observation.json"
    evidence_id = rules.check_observation(observation, job, workflow.DIGEST)
    if record.get("rules_sha256") != current_rules["sha256"]:
        raise ValueError("worker manifest is missing its assigned rules acknowledgement")
    for name in (build, manifest, record["evidence"], record["source"]):
        file = (checkout / name).resolve()
        if not file.is_relative_to(scope) or not file.is_file():
            raise ValueError(f"Missing or out-of-scope reconstruction file {name!r}")
    if evidence_id not in (checkout / record["evidence"]).read_text(encoding="utf-8"):
        raise ValueError("function evidence must cite the returned REA observation")
    git(checkout, "add", "--", directory)
    paths = git(checkout, "diff", "--cached", "--name-only", "-z").split("\0")
    if any(p and not p.startswith(directory + "/") for p in paths):
        raise ValueError("Worker staged changes outside the assigned reconstruction.")
    git(checkout, "-c", "user.name=Army Men RTS worker", "-c", "user.email=worker@localhost",
        "-c", "commit.gpgsign=false", "commit", "-m", f"Reconstruct function at RVA {address}")
    commit = git(checkout, "rev-parse", "HEAD")
    patch = attempt / "candidate.patch"
    with patch.open("wb") as output:
        subprocess.run(["git", "-C", str(checkout), "diff", "--binary", revision, commit],
                       check=True, stdout=output)
    return {"disposition": "candidate", "commit": commit, "manifest": manifest, "build": build,
            "observation": str(observation), "evidence_id": evidence_id, "rules_sha256": current_rules["sha256"],
            "patch": str(patch), "evidence": record["evidence"], "build_log": str(log)}


def worker(db, slot, number, private, watch, stop):
    import workflow

    owner = f"slot-{number:02d}-{uuid.uuid4().hex[:8]}"
    failures = 0
    while not stop.is_set():
        job = workflow.claim(db, owner)
        if not job:
            if not watch:
                break
            stop.wait(3)
            continue
        attempt = private / str(job["attempt"])
        try:
            attempt.mkdir(parents=True, exist_ok=False)
            result = run_job(db, job, slot, attempt, stop)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError, TimeoutError) as exc:
            detail = str(exc)
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                detail += ": " + str(exc.stderr).strip()
            result = {"disposition": "failed", "note": detail, "build_log": str(attempt / "worker.log")}
            failures += 1
        result.update({"attempt": job["attempt"], "base_revision": job["base_revision"]})
        if attempt.is_dir():
            (attempt / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        try:
            workflow.submit(db, job, result)
        except ValueError as exc:
            failures += 1
            print(f"{owner}: {exc}", file=sys.stderr)
        print(f"{owner} job {job['id']} {result['disposition']} {result.get('note', '')}", flush=True)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "workers.example.json")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--attempts", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate runners without taking jobs")
    parser.add_argument("--watch", action="store_true", help="Keep polling after the queue empties")
    args = parser.parse_args()
    slots = configuration(args.config)
    if args.check:
        for number, slot in enumerate(slots, 1):
            print(f"{number:02d} {slot['runner']} {slot.get('model', '(default)')} {slot['launcher'][0]}")
        return 0
    import workflow

    db = (args.db or workflow.DB).resolve()
    private = (args.attempts or db.parent / "attempts").resolve()
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=len(slots)) as executor:
        active = {executor.submit(worker, db, slot, i, private, args.watch, stop)
                  for i, slot in enumerate(slots, 1)}
        failures = 0
        try:
            while active:
                finished, active = wait(active, timeout=0.5, return_when=FIRST_COMPLETED)
                failures += sum(f.result() for f in finished)
            return int(failures > 0)
        finally:
            stop.set()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
