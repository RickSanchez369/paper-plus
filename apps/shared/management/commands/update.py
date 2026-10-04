"""One command to apply a new release: `python manage.py update`.

Order matters: back up first (so a bad migration is recoverable), then
migrate, then collect static files, then run the deployment checks. On
SQLite the backup is a copy of the database file (restore = put it back).
"""

import shutil
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.shared.backup import backup_filename, build_backup


class Command(BaseCommand):
    help = "Back up, migrate, collect static files and check -- run after every code update."

    def add_arguments(self, parser):
        parser.add_argument("--no-backup", action="store_true", help="Skip the safety backup.")

    def handle(self, *args, **options):
        if not options["no_backup"]:
            directory = Path(settings.BACKUP_DIR)
            directory.mkdir(parents=True, exist_ok=True)
            if connection.vendor == "sqlite":
                # The new code cannot read the OLD schema (a column it expects is not there until
                # migrate runs), so the JSON backup would fail exactly when it matters. Copy the
                # database file itself, through SQLite's own online-backup API (D-091).
                stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
                target = directory / f"before-update-{stamp}.sqlite3"
                source = sqlite3.connect(settings.DATABASES["default"]["NAME"])
                copy = sqlite3.connect(target)
                with copy:
                    source.backup(copy)
                copy.close()
                source.close()
            else:
                target = directory / ("before-update-" + backup_filename())
                with build_backup() as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out)
            self.stdout.write(f"Safety backup: {target}")
        call_command("migrate", interactive=False)
        call_command("collectstatic", interactive=False, verbosity=0)
        call_command("check", deploy=not settings.DEBUG)
        self.stdout.write(self.style.SUCCESS("Update complete. Restart the app (see deploy/UPDATING.md)."))
