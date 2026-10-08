"""Serve the throwaway QA database to a real phone on the same Wi-Fi: 0.0.0.0:8010, any Host header allowed.

    python tools/qa/run_phone_server.py      # then open http://<this PC's LAN IP>:8010 on the phone

Throwaway data only (tools/qa/.qa.sqlite3); never point this at the real database -- it accepts any Host.
"""
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[2]
os.environ["DATABASE_URL"] = "sqlite:///" + (root / "tools" / "qa" / ".qa.sqlite3").as_posix()
os.environ.update(DEBUG="True", ALLOWED_HOSTS="*", SECRET_KEY=os.environ.get("SECRET_KEY", "throwaway-qa"))
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.management import execute_from_command_line  # noqa: E402

execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8010", "--noreload"])
