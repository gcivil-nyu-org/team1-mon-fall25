# events/algolia_index.py
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register
from .models import Event

@register(Event)

class EventIndex(AlgoliaIndex):
    fields = ('title', 'description', 'date_str', 'time_str', 'location')
    settings = {
        'searchableAttributes': ['title', 'description', 'location'],
    }
    index_name = 'simpletix_events'

    #index_name = 'events'


    # custom field conversion
    def get_date_str(self, obj):
        return obj.date.isoformat() if obj.date else None

    def get_time_str(self, obj):
        return obj.time.strftime("%H:%M:%S") if obj.time else None


