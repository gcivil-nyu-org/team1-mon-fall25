# events/algolia_index.py
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register
from .models import Event


@register(Event)
class EventIndex(AlgoliaIndex):
    fields = ("title", "description", "date_str", "time_str", "location")
    settings = {
        "searchableAttributes": ["title", "description", "location"],
    }

    # NOTE: Manual prefix alignment for Algolia index name.
    # Context:
    # The backend (via algoliasearch_django) automatically prefixes index names using
    # ALGOLIA_INDEX_PREFIX (e.g. "simpletix_"). However, the frontend search client was
    # querying the base index name ("events"), leading to empty search results despite
    # successful CRUD operations.
    #
    # Fix:
    # I manually append "simpletix_" in the frontend (nav.html) so searches target
    # the same Algolia index ("simpletix_simpletix_events") used by the backend.
    # This keeps search and CRUD in sync across environments.
    #
    # Example resulting index:
    #   ALGOLIA_INDEX_PREFIX = "simpletix"
    #   final index_name     = "simpletix_simpletix_events"

    index_name = "simpletix_events"

    # custom field conversion
    def get_date_str(self, obj):
        return obj.date.isoformat() if obj.date else None

    def get_time_str(self, obj):
        return obj.time.strftime("%H:%M:%S") if obj.time else None
