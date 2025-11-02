# events/apps.py
import os
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        # Skip Algolia wiring in CI / tests
        if os.environ.get("DJANGO_DISABLE_ALGOLIA"):
            return

        # Local/dev: register index
        try:
            import events.algolia_index  # noqa: F401
        except Exception:
            # don’t break app startup if Algolia isn’t configured
            pass
