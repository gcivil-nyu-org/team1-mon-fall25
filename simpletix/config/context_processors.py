from django.conf import settings

def algolia_settings(request):
    return {
        "ALGOLIA_APP_ID": settings.ALGOLIA.get("APPLICATION_ID", ""),
        "ALGOLIA_SEARCH_KEY": settings.ALGOLIA.get("SEARCH_KEY", ""),
        "ALGOLIA_INDEX": f"{settings.ALGOLIA.get('INDEX_PREFIX', 'simpletix')}_events",
    }
