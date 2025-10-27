import pytest
from events.models import Event
from django.utils import timezone


@pytest.mark.django_db
def test_event_creation():
    event = Event.objects.create(
        title="Sample Event",
        description="This is a test event",
        date=timezone.now().date(),
        time=timezone.now().time(),
        location="NYC",
    )
    assert event.title == "Sample Event"
    assert str(event) == "Sample Event"
