from django.apps import AppConfig
import os


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        Make Algolia optional in local/dev.

        If ALGOLIA_APP_ID is not set or DJANGO_DISABLE_ALGOLIA is true,
        we skip importing events.algolia_index so Django can start.
        """
        disable = os.getenv("DJANGO_DISABLE_ALGOLIA")
        app_id = os.getenv("ALGOLIA_APP_ID")

        # In local dev, we usually have no Algolia config → just skip.
        if disable or not app_id:
            return

        try:
            import events.algolia_index  # noqa: F401
        except Exception:
            # Never block app startup because of Algolia issues
            return
