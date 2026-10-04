"""Start the business data from zero, keeping the user accounts: `python manage.py reset_business_data`.

Deletes every product, customer, supplier, invoice, payment, cheque, expense, return,
stock movement, price history, audit log and counter (invoice numbers restart). Keeps
users (phone + password), their permissions and the schema. A copy of the SQLite
database file is written to BACKUP_DIR first, so the reset can be undone by putting
that file back. Asks for a typed confirmation unless --yes is given.

Built for the owner's request to re-enter real data from scratch (2026-10-05).
"""

import sqlite3
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

# Business apps whose every table is emptied; users/auth/sessions/contenttypes/migrations are kept.
WIPED_APPS = ("returns", "payments", "sales", "purchasing", "inventory", "partners", "products", "shared", "admin")
CONFIRM_WORD = "RESET"


class Command(BaseCommand):
    help = "Delete all business data (keeps user accounts). Backs up the SQLite file first."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation.")

    def _models(self):
        return [m for m in apps.get_models() if m._meta.app_label in WIPED_APPS and not m._meta.proxy and m._meta.managed]

    def handle(self, *args, **options):
        models = self._models()
        counts = {m._meta.label: m._base_manager.count() for m in models}
        total = sum(counts.values())
        self.stdout.write(f"Rows to delete: {total} in {len([c for c in counts.values() if c])} tables. Users are kept.")
        if not options["yes"]:
            answer = input(f'Type {CONFIRM_WORD} to delete all business data: ')
            if answer.strip() != CONFIRM_WORD:
                raise CommandError("Cancelled; nothing was deleted.")

        if connection.vendor == "sqlite":
            directory = Path(settings.BACKUP_DIR)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"before-reset-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}.sqlite3"
            source, copy = sqlite3.connect(settings.DATABASES["default"]["NAME"]), sqlite3.connect(target)
            with copy:
                source.backup(copy)
            copy.close()
            source.close()
            self.stdout.write(f"Backup of the database file: {target}")

        # The ledgers protect each other (PROTECT foreign keys); everything goes, so the
        # checks are switched off for the delete and verified again before commit.
        with connection.constraint_checks_disabled():
            with transaction.atomic():
                for model in models:
                    model._base_manager.all()._raw_delete(connection.alias)
                connection.check_constraints()
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("VACUUM")
        left = sum(m._base_manager.count() for m in models)
        users = apps.get_model(settings.AUTH_USER_MODEL)._base_manager.count()
        self.stdout.write(self.style.SUCCESS(f"Done: {total - left} rows deleted, {users} user account(s) kept."))
