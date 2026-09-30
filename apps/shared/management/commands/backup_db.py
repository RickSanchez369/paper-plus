"""Write a backup zip to disk: `python manage.py backup_db [--dir PATH]`."""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.shared.backup import backup_filename, build_backup


class Command(BaseCommand):
    help = "Write a full backup (database + uploaded receipts) as a zip file."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=str(settings.BACKUP_DIR), help="Where to write the zip.")

    def handle(self, *args, **options):
        directory = Path(options["dir"])
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / backup_filename()
        with build_backup() as source, open(target, "wb") as out:
            shutil.copyfileobj(source, out)
        self.stdout.write(self.style.SUCCESS(f"Backup written: {target}"))
