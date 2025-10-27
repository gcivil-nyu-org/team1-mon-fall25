from django.apps import AppConfig
import os

class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        # Only import Algolia index when not in CI
        if not os.environ.get("CI"):
            import events.algolia_index  # noqa: F401
