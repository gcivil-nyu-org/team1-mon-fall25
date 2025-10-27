import pytest
from events.forms import EventForm


@pytest.mark.django_db
def test_event_form_valid():
    form = EventForm(
        data={"title": "Test Event", "description": "Testing form", "location": "NYC"}
    )
    assert form.is_valid()
