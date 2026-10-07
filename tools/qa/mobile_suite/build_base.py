"""Build the base throwaway DB of the mobile suite: schema, demo users/accounts/products, a demo week, then the rich data.

    python tools/qa/mobile_suite/build_base.py [NAME]     # -> tools/qa/.mobile/suite/NAME.sqlite3 (+ .login.txt); NAME=base
    python tools/qa/mobile_suite/build_base.py empty      # schema + user + accounts only (empty-state pages)
"""
import os
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[3]
name = sys.argv[1] if len(sys.argv) > 1 else "base"
folder = root / "tools" / "qa" / ".mobile" / "suite"
folder.mkdir(parents=True, exist_ok=True)
db = folder / f"{name}.sqlite3"
for suffix in ("", "-wal", "-shm"):
    p = pathlib.Path(str(db) + suffix)
    if p.exists():
        p.unlink()
env = dict(os.environ, QA_DB=str(db), PYTHONIOENCODING="utf-8", DEBUG="True")
steps = [["tools/qa/run_qa_server.py", "migrate"]]
if name == "empty":
    steps.append(["tools/qa/mobile_suite/seed_user_only.py"])
else:
    steps += [["tools/qa/seed_qa_db.py"], ["tools/qa/seed_demo_data.py"], ["tools/qa/mobile_suite/seed_rich.py"]]
for step in steps:
    r = subprocess.run([sys.executable, *step], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
    tail = (r.stdout or "").strip().splitlines()[-4:]
    print(step[-1], "->", r.returncode, *tail, sep="\n   ")
    if r.returncode:
        print(r.stderr[-1500:])
        sys.exit(1)
print("built", db)
