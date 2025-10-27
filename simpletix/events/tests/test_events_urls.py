from django.urls import reverse, resolve
from events import views


def test_event_list_url_resolves():
    url = reverse("events:event_list")
    assert resolve(url).func == views.event_list
