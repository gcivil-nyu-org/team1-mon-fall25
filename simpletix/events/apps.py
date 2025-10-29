import sys
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        # Only import Algolia index if not running tests
        if "pytest" not in sys.modules:
            try:
                import events.algolia_index  # noqa: F401
            except ModuleNotFoundError:
                pass  # skip if module not present
