"""
Generate PROJECT_MAP.md: file tree, settings, models and public functions.

Run from the project root, with the venv active, before starting a new chat:
    python tools/project_map.py

Everything is read from the live code (Django's model registry and the
modules themselves), so the map cannot go stale the way a hand-written
document does. Output is UTF-8 without BOM, so Persian labels survive.
"""
import importlib
import inspect
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Next to the other chat documents, so all five uploads live in docs/.
OUTPUT = ROOT / "docs" / "PROJECT_MAP.md"

# Folders never listed: environments, caches, database dumps, editor state.
SKIP_DIRS = {".venv", ".git", "__pycache__", "backups", "node_modules", ".idea", ".vscode"}
# Files never listed. `.env` holds secrets; the map must never point at it.
SKIP_FILES = {".env"}
# Per-app modules whose public functions are listed with their signatures.
API_MODULES = ("services", "selectors", "utils", "permissions")
# Only our own apps are mapped, not django.contrib or third-party apps.
LOCAL_PREFIX = "apps."

# Django must be configured before any model can be imported.
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402


def build_tree():
    """Indented project tree, skipping SKIP_DIRS and SKIP_FILES."""
    lines = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Pruning in place stops os.walk from descending into skipped folders.
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        relative = Path(dirpath).relative_to(ROOT)
        depth = len(relative.parts)
        if depth:
            lines.append(f"{'  ' * (depth - 1)}{relative.name}/")
        for name in sorted(filenames):
            if name in SKIP_FILES or name.endswith(".pyc"):
                continue
            lines.append(f"{'  ' * depth}{name}")
    return lines


def describe_field(field):
    """One line per forward field: name, type, relation, flags, choices, label."""
    parts = [f"`{field.name}`", type(field).__name__]
    if field.is_relation and field.related_model is not None:
        parts.append(f"-> {field.related_model._meta.label}")
        # Many-to-many relations have no on_delete.
        on_delete = getattr(field.remote_field, "on_delete", None)
        if on_delete is not None:
            parts.append(on_delete.__name__)
        if field.remote_field.related_name:
            parts.append(f"related_name={field.remote_field.related_name}")
    if getattr(field, "primary_key", False):
        parts.append("pk")
    elif getattr(field, "unique", False):
        parts.append("unique")
    if getattr(field, "null", False):
        parts.append("null")
    if getattr(field, "blank", False):
        parts.append("blank")
    if getattr(field, "choices", None):
        values = ", ".join(repr(value) for value, _ in field.choices)
        parts.append(f"choices=[{values}]")
    parts.append(f"«{field.verbose_name}»")
    return "- " + " | ".join(parts)


def describe_model(model):
    """Markdown block for one model: fields, reverse relations, constraints."""
    meta = model._meta
    lines = [f"### {meta.label} «{meta.verbose_name}»", f"table: `{meta.db_table}`", ""]

    for field in list(meta.fields) + list(meta.many_to_many):
        lines.append(describe_field(field))

    # Reverse accessors, e.g. user.memberships. Needed to write queries
    # without guessing related names.
    reverse = [f for f in meta.get_fields() if f.auto_created and not f.concrete]
    if reverse:
        lines.append("")
        lines.append("Reverse relations:")
        for rel in reverse:
            lines.append(f"- `{rel.get_accessor_name()}` <- {rel.related_model._meta.label}")

    rules = []
    for constraint in meta.constraints:
        detail = getattr(constraint, "fields", None) or getattr(constraint, "condition", "")
        rules.append(f"- {type(constraint).__name__} `{constraint.name}`: {detail}")
    for index in meta.indexes:
        rules.append(f"- Index `{index.name}`: {index.fields}")
    for group in meta.unique_together:
        rules.append(f"- unique_together: {group}")
    if rules:
        lines.append("")
        lines.append("Constraints and indexes:")
        lines.extend(rules)

    lines.append("")
    return lines


def describe_functions(app_config):
    """Public functions of the app's API modules, with signature and summary."""
    lines = []
    for module_name in API_MODULES:
        dotted = f"{app_config.name}.{module_name}"
        try:
            module = importlib.import_module(dotted)
        except ModuleNotFoundError as error:
            # Skip only when this module is absent; re-raise broken imports inside it.
            if error.name == dotted:
                continue
            raise
        for name, func in inspect.getmembers(module, inspect.isfunction):
            # Skip private helpers and names imported from other modules.
            if name.startswith("_") or func.__module__ != module.__name__:
                continue
            doc = inspect.getdoc(func)
            summary = f" — {doc.splitlines()[0]}" if doc else ""
            lines.append(f"- `{dotted}.{name}{inspect.signature(func)}`{summary}")
    return lines


def main():
    local_apps = sorted(
        (c for c in apps.get_app_configs() if c.name.startswith(LOCAL_PREFIX)),
        key=lambda c: c.name,
    )
    models = sorted(
        (m for c in local_apps for m in c.get_models()),
        key=lambda m: m._meta.label,
    )

    lines = [
        "# Project map",
        "",
        f"Generated {date.today().isoformat()} by `tools/project_map.py`. Do not edit by hand.",
        "",
        "## Settings",
        f"- Django {django.get_version()}, Python {sys.version.split()[0]}",
        f"- AUTH_USER_MODEL: `{settings.AUTH_USER_MODEL}`",
        f"- LANGUAGE_CODE: `{settings.LANGUAGE_CODE}`, TIME_ZONE: `{settings.TIME_ZONE}`",
        f"- Local apps: {', '.join(c.name for c in local_apps)}",
        "",
        "## File tree",
        "```",
        *build_tree(),
        "```",
        "",
        "## Models",
        "",
    ]
    for model in models:
        lines.extend(describe_model(model))

    lines.append("## Public functions")
    function_count = 0
    for app_config in local_apps:
        functions = describe_functions(app_config)
        function_count += len(functions)
        lines.extend(functions)
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"PROJECT_MAP.md written: {len(models)} models, {function_count} functions")


if __name__ == "__main__":
    main()