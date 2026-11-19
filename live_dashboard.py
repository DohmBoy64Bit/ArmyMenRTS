"""Mirror verified progress and scheduler activity to the dashboard and GitHub Pages."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

import workflow as w

DOCS = w.ROOT / "docs"
PAGES = w.ROOT / ".army/pages"


def read_queue():
    with w.transaction(w.DB) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id,rva,size,name,state,owner,expires FROM jobs ORDER BY id")]


def recent_events():
    with w.transaction(w.DB) as conn:
        return [dict(row) for row in conn.execute("""SELECT h.event, h.at, j.name, j.rva
            FROM history h JOIN jobs j ON j.id=h.job_id
            WHERE h.event IN ('claim','submitted','review','integrated')
            ORDER BY h.at DESC,h.rowid DESC LIMIT 100""")]


def worker_slots(jobs, now):
    slots = [{"slot": i, "job": None} for i in range(1, 11)]
    for job in jobs:
        owner = re.fullmatch(r"slot-(\d{2})-[0-9a-f]+", job["owner"] or "")
        if job["state"] != "leased" or not owner or job["expires"] <= now:
            continue
        index = int(owner[1])-1
        if 0 <= index < len(slots):
            slots[index].update(job={key: job[key] for key in ("name","rva","size")},
                                expires=int(job["expires"]))
    return slots


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(value, file, indent=2)
        file.write("\n")
    os.replace(file.name, path)


def publish():
    remote = w.git("remote", "get-url", "origin")
    if not (PAGES / ".git").is_dir():
        PAGES.mkdir(parents=True, exist_ok=True)
        w.git("init", "-b", "gh-pages", cwd=PAGES)
    refs = w.git("ls-remote", "--heads", remote, "gh-pages", cwd=PAGES)
    if refs:
        w.git("fetch", remote, "refs/heads/gh-pages", cwd=PAGES)
        w.git("merge", "--ff-only", "FETCH_HEAD", cwd=PAGES)
    # Ship only committed site assets and the files named by the public report.
    assets = w.git("ls-tree","-r","--name-only","HEAD","--","docs").splitlines()
    for tracked in assets:
        name = Path(tracked).relative_to("docs")
        if name.parts[0] == "proof" or name.as_posix() in ("progress.json","workers.json"):
            continue
        dest = PAGES/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git","show","HEAD:"+tracked], cwd=w.ROOT))
    report = json.loads((DOCS/"progress.json").read_text(encoding="utf-8"))
    paths = {"progress.json","workers.json"}
    for row in report["functions"]:
        for key in ("public_evidence","public_source"):
            if key in row:
                if not re.fullmatch(r"proof/[a-f0-9]{40,64}/[a-f0-9]{8}/(evidence|source)\.txt",row[key]):
                    raise ValueError("unexpected public proof path")
                paths.add(row[key])
    for name in paths:
        dest = PAGES/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((DOCS/name).read_bytes())
    (PAGES/".nojekyll").touch()
    w.git("add","--all",cwd=PAGES)
    if w.git("diff","--cached","--name-only",cwd=PAGES):
        w.git("commit","-m","Publish dashboard snapshot",cwd=PAGES)
    w.git("push", remote,"HEAD:refs/heads/gh-pages",cwd=PAGES)


def run(push, once):
    verified_key = queue_key = pool_key = None
    last_push = last_workers = 0
    pending = False
    while True:
        try:
            jobs = read_queue()
            now = time.time()
            tree = w.git("rev-parse","HEAD:reconstruction")
            ledger = [(j["rva"],j["size"],j["name"],j["state"]) for j in jobs]
            if tree != verified_key:
                w.snapshot(DOCS/"progress.json")
                verified_key, queue_key, pending = tree, ledger, True
            elif ledger != queue_key:
                path = DOCS/"progress.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                matched = [f for f in data["functions"] if f["status"]=="matched"]
                known = {f["rva"] for f in matched}
                data["functions"] = matched + [dict(rva=r,size=s,name=n,status=st)
                    for r,s,n,st in ledger if r not in known]
                atomic_json(path,data)
                queue_key, pending = ledger, True
            slots = worker_slots(jobs,now)
            assignments = [s["job"] for s in slots]
            events = recent_events()
            activity = (assignments,events)
            if activity != pool_key or (any(assignments) and now-last_workers >= 60):
                atomic_json(DOCS/"workers.json",dict(slots=slots,events=events,updated_at=datetime.now(timezone.utc).isoformat()))
                pool_key, last_workers, pending = activity, now, True
            if push and pending and now-last_push >= 60:
                publish()
                last_push, pending = now, False
            if once:
                return
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            if once:
                raise
            print(f"Dashboard update pending: {error}", flush=True)
            time.sleep(25)
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--push",action="store_true",help="Publish changed snapshots to origin/gh-pages")
    parser.add_argument("--once",action="store_true",help="Update once and exit")
    args = parser.parse_args()
    run(args.push,args.once)
