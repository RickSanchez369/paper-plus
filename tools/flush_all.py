"""
Empty every table in the database, keeping the schema and the applied-
migration history.

WHY this exists instead of `manage.py flush`: flush only truncates tables
Django still has a model for, and PostgreSQL then refuses the statement
whenever a table *outside* that list holds a foreign key into one inside it.
That happens on purpose during the single-business rebuild — the models are
deleted from the code before the migration drops their tables, so
`shared_business` & co. sit there as orphans pointing at `users_user`.
This script truncates every table in the schema with CASCADE, so orphans are
no obstacle, and skips `django_migrations` so Django does not forget which
migrations are applied.

Destructive and not undoable. Take a backup first (tools/backup.ps1).

Run from the project root, with the venv active:
    python tools/flush_all.py --yes
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Migration history must survive: it describes the schema that stays behind.
KEEP = {"django_migrations"}

sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402


def main():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = current_schema()
            ORDER BY tablename
            """
        )
        tables = [row[0] for row in cursor.fetchall() if row[0] not in KEEP]

        if not tables:
            print("nothing to truncate")
            return

        print(f"{len(tables)} tables would be emptied:")
        for name in tables:
            print(f"  {name}")

        if "--yes" not in sys.argv:
            print("\nnothing done. re-run with --yes to actually empty them.")
            return

        quoted = ", ".join(f'"{name}"' for name in tables)
        cursor.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
        print(f"\ntruncated {len(tables)} tables")


if __name__ == "__main__":
    main()
