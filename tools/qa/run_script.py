"""Run one qa_*.py scenario script against a THROWAWAY SQLite copy of the suite's demo database, never the .env database.

    python tools/qa/run_script.py qa_29_input_bounds.py [more.py ...]

`manage.py shell` alone reads DATABASE_URL from .env (PostgreSQL dev data); the scripts roll back, but there is no reason to touch it.
The copy comes from tools/qa/.mobile/suite/base.sqlite3 (built by `python tools/qa/mobile_suite/run.py --rebuild`).
"""
import os
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[2]
src = root / "tools" / "qa" / ".mobile" / "suite" / "base.sqlite3"
if not src.exists():
    sys.exit("no demo database yet: run  python tools/qa/mobile_suite/run.py --rebuild --only pages --smoke  first")
dst = root / "tools" / "qa" / ".mobile" / "qa-run.sqlite3"
shutil.copy(src, dst)
env = dict(os.environ, DATABASE_URL="sqlite:///" + dst.as_posix(), DEBUG="True", SECRET_KEY=os.environ.get("SECRET_KEY", "throwaway-qa"), PYTHONIOENCODING="utf-8")
code = 0
for name in sys.argv[1:]:
    path = name if os.path.sep in name or "/" in name else f"tools/qa/{name}"
    code |= subprocess.run([sys.executable, "manage.py", "shell", "-c", f"exec(open({path!r}, encoding='utf-8').read())"], cwd=root, env=env).returncode
sys.exit(code)
