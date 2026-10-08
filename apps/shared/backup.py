# path: apps/shared/backup.py

"""Whole-business backup: one zip with the data and the uploaded receipts.

Portable on purpose (Django's own JSON serialisation, no pg_dump): it works
on any host that can run the app, and a restore does not care which
PostgreSQL version wrote it. The zip holds

  manifest.json   when, by which code version, row counts (sanity check)
  database.json   every row of every app model
  media/...       uploaded files (expense receipts)

Restore = migrate an empty database, then `restore_db <zip>`.
"""

import json
import tempfile
import zipfile
from io import StringIO
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

from apps.shared.models import DocumentSequence

# Rebuilt by migrate / on login, so carrying them only bloats the file and
# can collide on restore.
EXCLUDED_MODELS = ("contenttypes", "auth.Permission", "sessions", "admin.LogEntry")

FORMAT_VERSION = 1


def backup_filename(now=None):
    now = timezone.localtime(now or timezone.now())
    return f"paper-plus-backup-{now:%Y-%m-%d_%H%M}.zip"


def _dump_json():
    out = StringIO()
    call_command(
        "dumpdata",
        exclude=list(EXCLUDED_MODELS),
        natural_foreign=True,
        natural_primary=True,
        use_base_manager=True,
        stdout=out,
    )
    return out.getvalue()


def _row_counts(payload):
    counts = {}
    for row in json.loads(payload):
        counts[row["model"]] = counts.get(row["model"], 0) + 1
    return counts


def build_backup():
    """Return an open, rewound temporary file holding the zip (caller closes it)."""
    payload = _dump_json()
    manifest = {
        "format": FORMAT_VERSION,
        "created_at": timezone.now().isoformat(),
        "django": django.get_version(),
        "database": connection.vendor,
        "rows": _row_counts(payload),
    }
    handle = tempfile.TemporaryFile()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("database.json", payload)
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.is_dir():
            for path in sorted(media_root.rglob("*")):
                if path.is_file():
                    archive.write(path, "media/" + path.relative_to(media_root).as_posix())
    handle.seek(0)
    return handle


def restore_backup(path):
    """Load a backup into the current database. Refuses a non-empty one.

    The business tables must be empty: loading over existing rows would
    silently mix two histories. Returns the manifest.
    """
    from apps.users.models import User

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "manifest.json" not in names or "database.json" not in names:
            raise ValueError("این فایل یک پشتیبان معتبر کاغذ پلاس نیست.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != FORMAT_VERSION:
            raise ValueError("نسخهٔ فرمت این پشتیبان پشتیبانی نمی‌شود.")
        if User.objects.exists():
            raise ValueError("پایگاه داده خالی نیست؛ بازیابی فقط روی پایگاه خالی انجام می‌شود.")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "database.json"
            target.write_bytes(archive.read("database.json"))
            with transaction.atomic():
                # migrate seeds the numbering rows; the backup carries the real ones.
                DocumentSequence.objects.all().delete()
                call_command("loaddata", str(target), verbosity=0)

        media_root = Path(settings.MEDIA_ROOT).resolve()
        for name in names:
            if not name.startswith("media/") or name.endswith("/"):
                continue
            destination = (media_root / name[len("media/"):]).resolve()
            if media_root not in destination.parents:   # zip-slip guard
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
    return manifest


def business_model_labels():
    """Every model that goes into a backup, for the page's "what's inside" list."""
    return sorted(
        model._meta.label
        for model in apps.get_models()
        if model._meta.app_label not in ("contenttypes", "sessions", "admin")
    )
