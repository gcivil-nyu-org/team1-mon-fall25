from django import template
from accounts.models import OrganizerProfile

register = template.Library()


@register.simple_tag(takes_context=True)
def get_profile(context):
    """
    Usage: {% get_profile as prof %}
    Returns the OrganizerProfile for the logged-in user or None.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return None
    try:
        return OrganizerProfile.objects.get(user=user)
    except OrganizerProfile.DoesNotExist:
        return None
