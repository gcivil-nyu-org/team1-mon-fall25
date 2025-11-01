# simpletix/events/apps.py
import os
import sys
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        Load Algolia integration only in local/dev/prod runs,
        skip in test/CI environments (like Travis).
        """

        # Skip if running in Travis CI, pytest, or explicitly disabled
        if (
            os.environ.get("CI") == "true"
            or os.environ.get("TRAVIS") == "true"
            or os.environ.get("DJANGO_DISABLE_ALGOLIA") == "1"
            or "pytest" in sys.modules
        ):
            return

        try:
            import events.algolia_index  # noqa: F401
        except ModuleNotFoundError:
            pass
