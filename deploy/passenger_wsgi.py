"""Entry point for hosts that run Python apps through Passenger (cPanel/DirectAdmin
"Setup Python App"). Copy this file to the project root under the same name.

Everything else (settings, secrets, database) comes from .env, so this file
never needs editing when the code is updated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from core.wsgi import application  # noqa: E402,F401
