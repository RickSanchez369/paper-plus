"""Build a THROWAWAY demo database and serve it, so several browser audits can run side by side.

    python tools/qa/mobile_env.py NAME PORT     # e.g. critic07 8107; blocks while serving

The database lives in tools/qa/.mobile/NAME.sqlite3 (git-ignored) and its login in
tools/qa/.mobile/NAME.sqlite3.login.txt (phone line, password line). The real database and .env are never touched.
"""
import os
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[2]
name, port = sys.argv[1], sys.argv[2]
folder = root / "tools" / "qa" / ".mobile"
folder.mkdir(exist_ok=True)
db = folder / f"{name}.sqlite3"
env = dict(os.environ, QA_DB=str(db), QA_PORT=port, PYTHONIOENCODING="utf-8", DEBUG="True")
py = sys.executable
if not db.exists():
    for step in (["tools/qa/run_qa_server.py", "migrate"], ["tools/qa/seed_qa_db.py"], ["tools/qa/seed_demo_data.py"]):
        subprocess.run([py, *step], cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
print(f"serving {db.name} on http://localhost:{port}", flush=True)
subprocess.run([py, "tools/qa/run_qa_server.py"], cwd=root, env=env, check=False)
