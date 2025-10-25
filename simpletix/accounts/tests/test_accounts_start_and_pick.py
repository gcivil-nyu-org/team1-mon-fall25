import pytest
from django.urls import reverse

APP = "accounts"


@pytest.mark.django_db
def test_start_has_three_role_options(client):
    res = client.get(reverse(f"{APP}:start"))
    assert res.status_code == 200
    body = res.content.lower()
    assert b"organizer" in body
    assert b"attendee" in body
    # guest may be "continue as guest" or "guest"
    assert b"guest" in body or b"continue as guest" in body


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["organizer", "attendee"])
def test_pick_role_redirects_to_login(client, role):
    res = client.get(reverse(f"{APP}:pick_role", args=[role]), follow=False)
    assert res.status_code in (302, 303)
    assert reverse(f"{APP}:login") in res["Location"]
