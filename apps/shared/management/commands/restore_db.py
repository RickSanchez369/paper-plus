"""Load a backup zip into an EMPTY, migrated database: `python manage.py restore_db FILE`."""

from django.core.management.base import BaseCommand, CommandError

from apps.shared.backup import restore_backup


class Command(BaseCommand):
    help = "Restore a backup zip made by backup_db / the backup page (empty database only)."

    def add_arguments(self, parser):
        parser.add_argument("file")

    def handle(self, *args, **options):
        try:
            manifest = restore_backup(options["file"])
        except (ValueError, OSError) as exc:
            raise CommandError(str(exc))
        total = sum(manifest["rows"].values())
        self.stdout.write(self.style.SUCCESS(f"Restored {total} rows from a backup made {manifest['created_at']}."))
