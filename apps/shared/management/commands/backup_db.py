"""Write a backup zip to disk: `python manage.py backup_db [--dir PATH] [--keep N]`.

`--keep N` (for a scheduled job) deletes the oldest backup zips in that folder beyond the newest N,
so a daily cron does not fill the disk. Only files named like our own backups are ever touched.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.shared.backup import backup_filename, build_backup


class Command(BaseCommand):
    help = "Write a full backup (database + uploaded receipts) as a zip file."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=str(settings.BACKUP_DIR), help="Where to write the zip.")
        parser.add_argument("--keep", type=int, default=0, help="Keep only the newest N backups there (0 = keep all).")

    def handle(self, *args, **options):
        directory = Path(options["dir"])
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / backup_filename()
        with build_backup() as source, open(target, "wb") as out:
            shutil.copyfileobj(source, out)
        self.stdout.write(self.style.SUCCESS(f"Backup written: {target}"))
        keep = options["keep"]
        if keep > 0:
            old = sorted(directory.glob("paper-plus-backup-*.zip"))[:-keep]
            for path in old:
                path.unlink()
            if old:
                self.stdout.write(f"Removed {len(old)} old backup(s), kept the newest {keep}.")
