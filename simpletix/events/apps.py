# simpletix/events/apps.py
import os
import sys
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        We only want to load Algolia in real app runs.
        For tests / CI / local scripts we must skip it,
        otherwise algoliasearch_django tries to create a client
        and crashes because ALGOLIA_APP_ID / API_KEY are missing.
        """

        # 1) CI env (GitHub, GitLab, etc.)
        if os.environ.get("CI") == "1":
            return

        # 2) explicit flag we can set when running pytest:
        #    DJANGO_DISABLE_ALGOLIA=1 pytest
        if os.environ.get("DJANGO_DISABLE_ALGOLIA") == "1":
            return

        # 3) running under pytest (like your case right now)
        if "pytest" in sys.modules:
            return

        # if none of the above, load Algolia normally
        try:
            import events.algolia_index  # noqa: F401
        except ModuleNotFoundError:
            # package not installed in this env – just ignore
            pass
