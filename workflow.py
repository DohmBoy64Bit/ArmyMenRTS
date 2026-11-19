"""Local coordinator and independent byte verifier for the Steam x86 build."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".army" / "queue.sqlite"
TARGET = Path(os.environ.get("AMRTS_TARGET", r"C:\Program Files (x86)\Steam\steamapps\common\Army Men RTS\amrts.exe"))
DIGEST = "34c9cacfcd42a816a5a9e886fbe18ae69ca2b82bdb7ed95588772f3079777b59"
LEASE = 900


@contextlib.contextmanager
def transaction(db):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(db, timeout=30)) as conn, conn:
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY, rva INTEGER, size INTEGER, name TEXT,
            base_revision TEXT, state TEXT DEFAULT 'queued', attempt TEXT,
            owner TEXT, expires REAL, result TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS history (
            job_id INTEGER, attempt TEXT, event TEXT, at REAL, detail TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS prerequisites (
            job_id INTEGER, predecessor INTEGER, PRIMARY KEY(job_id, predecessor))""")
        conn.execute("BEGIN IMMEDIATE")
        yield conn


def enqueue(db, rva, size, name, base_revision, after=()):
    if rva < 0 or size <= 0:
        raise ValueError("invalid function range")
    with transaction(db) as conn:
        if conn.execute("SELECT 1 FROM jobs WHERE rva < ? AND rva+size > ?", (rva+size, rva)).fetchone():
            raise ValueError("job overlaps an existing assignment")
        for predecessor in set(after):
            if not conn.execute("SELECT 1 FROM jobs WHERE id=?", (predecessor,)).fetchone():
                raise ValueError(f"unknown prerequisite job {predecessor}")
        job_id = conn.execute("INSERT INTO jobs(rva,size,name,base_revision) VALUES (?,?,?,?)",
                              (rva, size, name, base_revision)).lastrowid
        conn.executemany("INSERT INTO prerequisites VALUES (?,?)", [(job_id,k) for k in set(after)])
        return job_id


def claim(db, owner):
    now = time.time()
    with transaction(db) as conn:
        row = conn.execute("""SELECT * FROM jobs j WHERE (state='queued' OR
            (state='leased' AND expires<=?)) AND NOT EXISTS (
            SELECT 1 FROM prerequisites p JOIN jobs previous ON previous.id=p.predecessor
            WHERE p.job_id=j.id AND previous.state!='integrated') ORDER BY id LIMIT 1""", (now,)).fetchone()
        if row is None:
            return None
        attempt = uuid.uuid4().hex
        conn.execute("UPDATE jobs SET state='leased',owner=?,attempt=?,expires=? WHERE id=?",
                     (owner, attempt, now+LEASE, row["id"]))
        conn.execute("INSERT INTO history VALUES (?,?,?,?,?)", (row["id"], attempt, "claim", now, owner))
        return dict(conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())


def change_lease(db, job, state, result=None):
    now = time.time()
    payload = json.dumps(result) if result is not None else None
    with transaction(db) as conn:
        changed = conn.execute("""UPDATE jobs SET expires=?,state=?,result=?
            WHERE id=? AND attempt=? AND state='leased' AND expires>?""",
            (now+LEASE, state, payload, job["id"], job["attempt"], now)).rowcount
        if not changed:
            raise ValueError("expired or superseded lease")
        if result is not None:
            conn.execute("INSERT INTO history VALUES (?,?,?,?,?)",
                         (job["id"], job["attempt"], state, now, payload))


def renew(db, job):
    change_lease(db, job, "leased")


def submit(db, job, result):
    change_lease(db, job, "submitted" if result.get("commit") else "review", result)


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def target_image():
    data = TARGET.read_bytes()
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError("reference SHA-256 differs from the pinned Steam build")
    pe, = struct.unpack_from("<I", data, 60)
    count, = struct.unpack_from("<H", data, pe+6)
    opt, = struct.unpack_from("<H", data, pe+20)
    sections = []
    for i in range(count):
        p = pe+24+opt+40*i
        virtual, rva, raw, offset = struct.unpack_from("<IIII", data, p+8)
        flags, = struct.unpack_from("<I", data, p+36)
        if flags & 0x20 and raw:
            sections.append(dict(name=data[p:p+8].rstrip(b"\0").decode(), rva=rva,
                                 size=min(raw, virtual or raw), offset=offset))
    return data, sections


def location(sections, rva, size):
    for section in sections:
        delta = rva-section["rva"]
        if size > 0 and 0 <= delta and delta+size <= section["size"]:
            return section["offset"]+delta
    raise ValueError("range falls outside file-backed code")


def inside(tree, relative):
    path = (tree / relative).resolve()
    if not path.is_relative_to(tree.resolve()) or not path.is_file():
        raise ValueError(f"missing or invalid repository file: {relative}")
    return path


def verify_revision(revision, image, sections, required=None, image_result=None):
    revision = git("rev-parse", "--verify", revision+"^{commit}")
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        archive = temp / "source.zip"
        git("archive", "--format=zip", "-o", str(archive), revision)
        tree = temp / "src"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(tree)
        rows = []
        for path in sorted((tree/"reconstruction").rglob("function.json")):
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            rva, size = record["rva"], record["size"]
            offset = location(sections, rva, size)
            for key in ("source", "evidence"):
                inside(tree, record[key])
            builder = inside(tree, str(path.with_name("build.py").relative_to(tree)))
            with tempfile.TemporaryDirectory() as out:
                output = Path(out)/"code.bin"
                subprocess.run([sys.executable, str(builder), "--output", str(output)],
                               cwd=tree, check=True, timeout=180)
                candidate = output.read_bytes()
            if candidate != image[offset:offset+size]:
                raise ValueError(f"function byte mismatch at RVA {rva:#x}")
            if any(old["rva"] < rva+size and rva < old["rva"]+old["size"] for old in rows):
                raise ValueError("overlapping verified ranges")
            rows.append({**{k: record[k] for k in ("name","rva","size","source","evidence")},
                         "revision": revision, "status": "matched"})
        if required and not any((r["rva"],r["size"]) == required for r in rows):
            raise ValueError("candidate does not verify the assigned range")
        image_builder = tree / "reconstruction/build_image.py"
        if image_result is not None and image_builder.is_file():
            binary = temp / "rebuilt.exe"
            subprocess.run([sys.executable,str(image_builder),"--output",str(binary)],cwd=tree,
                           timeout=1800,check=True)
            rebuilt = binary.read_bytes()
            image_result.update(equal=rebuilt==image,sha256=hashlib.sha256(rebuilt).hexdigest())
        return sorted(rows, key=lambda row: row["rva"])


def snapshot(output):
    image, sections = target_image()
    image_result = {}
    rows = verify_revision("HEAD", image, sections, image_result=image_result)
    with transaction(DB) as conn:
        known = {r["rva"] for r in rows}
        for job in conn.execute("SELECT name,rva,size,state FROM jobs ORDER BY rva"):
            if job["rva"] not in known:
                rows.append(dict(name=job["name"], rva=job["rva"], size=job["size"], status=job["state"]))
    report = dict(target=dict(name="amrts.exe",sha256=DIGEST,size=len(image)),
                  sections=[{k:v for k,v in s.items() if k!="offset"} for s in sections],
                  code_bytes=sum(s["size"] for s in sections),
                  verified_bytes=sum(r["size"] for r in rows if r["status"]=="matched"),
                  whole_file_equal=image_result.get("equal",False),
                  rebuilt_sha256=image_result.get("sha256"),functions=rows)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(report, file, indent=2)
        file.write("\n")
    os.replace(file.name, path)
    return report


def integrate(job_id):
    with transaction(DB) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND state='submitted'", (job_id,)).fetchone()
        if not row:
            raise ValueError("job has no submitted candidate")
        job = dict(row)
    result = json.loads(job["result"])
    commit = git("rev-parse", "--verify", result["commit"]+"^{commit}")
    base = job["base_revision"]
    subprocess.run(["git","merge-base","--is-ancestor",base,commit], cwd=ROOT, check=True)
    prefix = f"reconstruction/{job['rva']:08x}/"
    paths = git("diff","--name-only",base,commit).splitlines()
    if not paths or any(not path.startswith(prefix) for path in paths):
        raise ValueError("candidate changes files outside its assigned function directory")
    if git("status","--porcelain","--untracked-files=no"):
        raise ValueError("integration requires a clean tracked working tree")
    head = git("rev-parse","HEAD")
    existing = bool(git("ls-tree","-r","--name-only",head,"--",prefix))
    if existing and git("diff","--name-only",head,commit,"--",prefix):
        raise ValueError("function directory already present with different contents")
    image, sections = target_image()
    with tempfile.TemporaryDirectory() as temp:
        checkout = Path(temp)/"checkout"
        git("worktree","add","--detach",str(checkout),head)
        try:
            if not existing:
                git("restore","--source",commit,"--staged","--worktree","--",prefix,cwd=checkout)
                git("commit","-m",f"Reconstruct {job['name']} at {job['rva']:#x}",cwd=checkout)
            merged = git("rev-parse","HEAD",cwd=checkout)
            verify_revision(merged,image,sections,(job["rva"],job["size"]))
            git("merge","--ff-only",merged)
        finally:
            git("worktree","remove","--force",str(checkout))
    with transaction(DB) as conn:
        conn.execute("UPDATE jobs SET state='integrated' WHERE id=? AND attempt=?", (job_id,job["attempt"]))
        conn.execute("""UPDATE jobs SET base_revision=? WHERE state='queued' AND id IN
            (SELECT job_id FROM prerequisites WHERE predecessor=?)""",(merged,job_id))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest="action",required=True)
    cmd.add_parser("baseline")
    add = cmd.add_parser("enqueue")
    add.add_argument("rva", type=lambda value:int(value,0))
    add.add_argument("size", type=lambda value:int(value,0))
    add.add_argument("name")
    add.add_argument("--after",type=int,action="append",default=[],metavar="JOB_ID")
    cmd.add_parser("status")
    req = cmd.add_parser("retry")
    req.add_argument("id", type=int)
    accept = cmd.add_parser("integrate")
    accept.add_argument("id", type=int)
    export = cmd.add_parser("report")
    export.add_argument("--output",default=str(ROOT/"docs/progress.json"))
    compare = cmd.add_parser("compare-image")
    compare.add_argument("candidate",type=Path)
    args = parser.parse_args()
    if args.action == "status":
        with transaction(DB) as conn:
            print(json.dumps([dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY id")],indent=2))
    elif args.action == "retry":
        with transaction(DB) as conn:
            if not conn.execute("""UPDATE jobs SET state='queued',base_revision=?,result=NULL
                WHERE id=? AND state IN ('review','submitted')""",(git("rev-parse","HEAD"),args.id)).rowcount:
                raise ValueError("only review or submitted jobs may be retried")
    elif args.action == "integrate":
        integrate(args.id)
    elif args.action == "report":
        report = snapshot(args.output)
        print(f"{report['verified_bytes']} of {report['code_bytes']} code bytes verified")
    else:
        image, sections = target_image()
        if args.action == "compare-image":
            other = args.candidate.read_bytes()
            print(f"Candidate SHA-256 {hashlib.sha256(other).hexdigest()}")
            if other != image:
                mismatch = next((i for i,(a,b) in enumerate(zip(image,other)) if a!=b),min(len(image),len(other)))
                raise ValueError(f"first difference at file offset {mismatch:#x}")
            print("Whole-file comparison is byte-identical.")
        elif args.action == "enqueue":
            location(sections,args.rva,args.size)
            print(enqueue(DB,args.rva,args.size,args.name,git("rev-parse","HEAD"),args.after))
        else:
            print(json.dumps(dict(sha256=DIGEST,size=len(image),sections=sections),indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        sys.exit(str(error))
