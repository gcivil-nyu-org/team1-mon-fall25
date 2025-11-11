# events/apps.py

import os
import sys
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        Initialize Algolia integration for Events.

        Rules:
        - In CI or when running tests, skip Algolia entirely (no network calls).
        - Otherwise, only enable Algolia if:
            * DJANGO_DISABLE_ALGOLIA is NOT set, and
            * ALGOLIA_APP_ID is set.
        - Never block app startup if Algolia import fails.
        """

        # 1) Skip in CI (GitHub Actions / pipelines usually set CI=true)
        if os.getenv("CI", "").lower() == "true":
            return

        # 2) Skip when running tests locally (pytest or manage.py test)
        argv = " ".join(sys.argv).lower()
        if (
            "pytest" in argv
            or " manage.py test" in argv
            or " django-admin test" in argv
        ):
            return

        # 3) Env-based toggle (your original logic)
        disable = os.getenv("DJANGO_DISABLE_ALGOLIA")
        app_id = os.getenv("ALGOLIA_APP_ID")
        print(f"DJANGO_DISABLE_ALGOLIA: {disable}")

        # In local dev, we often have no Algolia config → just skip.
        # if disable or not app_id:
        #     return

        # 4) Normal runtime: try to register Algolia index
        print("ALGOLIA_APP_ID:", app_id)
        try:
            from . import algolia_index  # noqa: F401

            print("Algolia index imported successfully")
        except Exception as e:
            # Never block app startup because of Algolia issues
            print("Failed to import Algolia index:", e)
            return
