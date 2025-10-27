import pytest
from django.urls import reverse
from events.models import Event
from django.utils import timezone

@pytest.mark.django_db
def test_event_list_view(client):
    url = reverse("events:event_list")
    response = client.get(url)
    assert response.status_code == 200
    assert "Upcoming Events" in response.content.decode()

@pytest.mark.django_db
def test_event_detail_view(client):
    event = Event.objects.create(
        title="Music Fest",
        description="Cool event",
        date=timezone.now().date(),
        time=timezone.now().time(),
        location="LA",
    )
    url = reverse("events:event_detail", args=[event.id])
    response = client.get(url)
    assert response.status_code == 200
    assert "Music Fest" in response.content.decode()
