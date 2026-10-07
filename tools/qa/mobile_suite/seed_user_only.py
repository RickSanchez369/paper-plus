"""A sign-in user only (no accounts, products or parties): the empty state of every page."""
import os
import pathlib
import random
import secrets
import sys

root = pathlib.Path(__file__).resolve().parents[3]
db = pathlib.Path(os.environ["QA_DB"])
os.environ["DATABASE_URL"] = "sqlite:///" + db.as_posix()
os.environ.setdefault("SECRET_KEY", "throwaway-qa")
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django  # noqa: E402

django.setup()
from apps.users.models import User  # noqa: E402

phone = f"09{random.randint(100000000, 999999999)}"
password = secrets.token_urlsafe(10)
User.objects.create_superuser(phone=phone, password=password)
(db.parent / (db.name + ".login.txt")).write_text(f"{phone}\n{password}\n", encoding="utf-8")
print("user only")
