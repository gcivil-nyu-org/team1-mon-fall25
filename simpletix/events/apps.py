# events/apps.py
import os
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        Register Algolia indexes only in real/runtime envs.
        Skip during tests/CI to avoid external HTTP calls.
        """
        disable = os.environ.get("DJANGO_DISABLE_ALGOLIA") or os.environ.get("CI")
        if disable:
            return

        # only import when not disabled
        try:
            import events.algolia_index  # noqa: F401
        except Exception:
            # don't blow up the app if Algolia isn't configured in local
            pass
