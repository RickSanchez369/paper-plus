"""Run the dev server against a THROWAWAY SQLite database, never the real one.

Browser QA needs real invoices, cheques and expenses, and those can never be
deleted once booked (append-only). So this wrapper points the app at
`QA_DB` (default: tools/qa/.qa.sqlite3, git-ignored) before Django starts,
leaves the PostgreSQL dev data alone, and serves on port 8001 (or `QA_PORT`, so several throwaway servers can run at once).

    python tools/qa/run_qa_server.py            # serve
    python tools/qa/run_qa_server.py migrate    # (re)build the schema first
"""
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[2]
db = pathlib.Path(os.environ.get("QA_DB", root / "tools" / "qa" / ".qa.sqlite3"))
os.environ["DATABASE_URL"] = "sqlite:///" + db.as_posix()
os.environ.setdefault("DEBUG", "True")
# A throwaway database needs no real secret; this keeps the script working without the real .env.
os.environ.setdefault("SECRET_KEY", "throwaway-qa")
sys.path.insert(0, str(root))
os.chdir(root)

from django.core.management import execute_from_command_line  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
if len(sys.argv) > 1 and sys.argv[1] == "migrate":
    execute_from_command_line(["manage.py", "migrate"])
else:
    execute_from_command_line(["manage.py", "runserver", os.environ.get("QA_PORT", "8001"), "--noreload"])
