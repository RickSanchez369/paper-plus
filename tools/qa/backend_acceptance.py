"""Run the backend acceptance scenarios against an isolated, newly migrated SQLite database."""

import os
from pathlib import Path
from runpy import run_path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = (
    "qa_02_purchase.py",
    "qa_03_sales.py",
    "qa_04_inventory.py",
    "qa_06_payments.py",
    "qa_10_admin.py",
    "qa_11_report_numbers.py",
    "qa_13_backup.py",
    "qa_14_invoice_print.py",
    "qa_26_returns.py",
    "qa_32_returns_v2.py",
)


def main():
    sys.path.insert(0, str(ROOT))
    with TemporaryDirectory(prefix="paper-plus-backend-") as temporary:
        directory = Path(temporary)
        database = directory / "qa.sqlite3"
        os.environ.update(
            DJANGO_SETTINGS_MODULE="core.settings",
            DATABASE_URL="sqlite:///" + database.as_posix(),
            QA_DB=database.as_posix(),
            SECRET_KEY="throwaway-backend-qa",
            DEBUG="True",
        )

        import django

        django.setup()
        from django.core.management import call_command
        from django.db import connections
        from django.test import override_settings

        from tools.qa.qa_lib import FAILS, RESULTS

        failures = 0
        checks = 0
        with override_settings(MEDIA_ROOT=directory / "media", BACKUP_DIR=directory / "backups"):
            try:
                call_command("migrate", interactive=False, verbosity=0)
                run_path(str(ROOT / "tools" / "qa" / "seed_qa_db.py"))
                call_command("check")
                for name in SCENARIOS:
                    FAILS.clear()
                    RESULTS.clear()
                    run_path(str(ROOT / "tools" / "qa" / name))
                    failures += len(FAILS)
                    checks += len(RESULTS)
            finally:
                connections.close_all()
        print(f"Backend acceptance: {checks - failures}/{checks} checks passed.")
        return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
