from django.apps import AppConfig


class SharedConfig(AppConfig):
    name = "apps.shared"

    def ready(self):
        """Register signal handlers (D-009 role -> Group sync)."""
        from . import signals  # noqa: F401