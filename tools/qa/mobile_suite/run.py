"""Run the mobile suite: builds the base DB once, gives every writing module its own DB copy + server, runs shards in parallel,
then adds everything up.

    python tools/qa/mobile_suite/run.py                 # everything
    python tools/qa/mobile_suite/run.py --only sale,forms --shards 3
    python tools/qa/mobile_suite/run.py --smoke         # a few units of each module (minutes, not an hour)

Throwaway databases only (tools/qa/.mobile/suite/*.sqlite3). The real database and .env are never read.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "tools" / "qa" / ".mobile" / "suite"
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT), DEBUG="True")

# module -> (writes?, default shards). Read-only modules share one server; writing ones get a DB copy + server per shard.
MODULES = {
    "pages": (False, 4),
    "links": (False, 1),
    "sale": (True, 4),
    "purchase": (True, 2),
    "forms": (True, 3),
    "payments": (True, 2),
    "interact": (False, 3),
    "states": (True, 1),
    "empty": (True, 1),
}


def copy_db(src_name, dst_name):
    for suffix in ("", "-wal", "-shm"):
        d = pathlib.Path(str(OUT / f"{dst_name}.sqlite3") + suffix)
        if d.exists():
            d.unlink()
    shutil.copy(OUT / f"{src_name}.sqlite3", OUT / f"{dst_name}.sqlite3")
    shutil.copy(OUT / f"{src_name}.sqlite3.login.txt", OUT / f"{dst_name}.sqlite3.login.txt")


def start_server(db_name, port):
    env = dict(ENV, QA_DB=str(OUT / f"{db_name}.sqlite3"), QA_PORT=str(port))
    log = open(OUT / f"srv-{db_name}.log", "w", encoding="utf-8")
    proc = subprocess.Popen([PY, "tools/qa/run_qa_server.py"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/login/", timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError(f"server for {db_name} did not start; see {log.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--shards", type=int, default=0, help="override shard count of every writing module")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--port-base", type=int, default=8700, help="first port; use another one to run next to a suite that is still going")
    ap.add_argument("--shard-index", type=int, default=-1, help="run only this shard of every chosen module (re-run one that crashed)")
    ap.add_argument("--tag", default="", help="prefix of the DB copies, so two runs never share one")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.rebuild or not (OUT / "base.sqlite3").exists():
        subprocess.run([PY, "tools/qa/mobile_suite/build_base.py", "base"], cwd=ROOT, env=ENV, check=True)
    for f in OUT.glob("*.jsonl"):
        if a.shard_index >= 0:
            if any(f.stem.endswith(f"-{a.shard_index}") and f.stem.startswith(m) for m in a.only.split(",")):
                f.unlink()
        elif not a.only or any(f.stem.startswith(m) for m in a.only.split(",")):
            f.unlink()
    names = [m for m in MODULES if not a.only or m in a.only.split(",")]
    servers, procs, port = [], [], a.port_base
    t0 = time.time()
    try:
        # one shared read-only server
        copy_db("base", a.tag + "ro")
        servers.append(start_server(a.tag + "ro", port))
        ro_base = f"http://localhost:{port}"
        port += 1
        for m in names:
            writes, default = MODULES[m]
            n = a.shards or default if writes or a.shards else default
            n = 1 if a.smoke else n
            for i in range(n):
                if a.shard_index >= 0 and i != a.shard_index:
                    continue
                if writes:
                    db = f"{a.tag}{m}{i}"
                    if m == "empty":
                        if not (OUT / "empty.sqlite3").exists() or a.rebuild:
                            subprocess.run([PY, "tools/qa/mobile_suite/build_base.py", "empty"], cwd=ROOT, env=ENV, check=True)
                        copy_db("empty", db)
                    else:
                        copy_db("base", db)
                    servers.append(start_server(db, port))
                    base = f"http://localhost:{port}"
                    port += 1
                else:
                    db, base = a.tag + "ro", ro_base
                cmd = [PY, "-m", f"tools.qa.mobile_suite.t_{m}", "--db", str(OUT / f"{db}.sqlite3"), "--base", base, "--shard", f"{i}/{n}"]
                if a.smoke:
                    cmd += ["--limit", "6"]
                log = open(OUT / f"log-{m}-{i}.txt", "w", encoding="utf-8")
                procs.append((m, i, subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)))
        print(f"started {len(procs)} workers on {len(servers)} servers", flush=True)
        for m, i, p in procs:
            p.wait()
            print(f"  worker {m}-{i} exit {p.returncode}  ({time.time() - t0:.0f}s)", flush=True)
    finally:
        for s in servers:
            s.kill()
    subprocess.run([PY, "tools/qa/mobile_suite/summarize.py"], cwd=ROOT, env=ENV)


if __name__ == "__main__":
    main()
