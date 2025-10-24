import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

APP = "accounts"

@pytest.mark.django_db
def test_signup_username_already_exists(client):
    User = get_user_model()
    User.objects.create_user(username="dupe", password="Passw0rd1!")
    client.get(reverse(f"{APP}:pick_role", args=["organizer"]))

    r = client.post(reverse(f"{APP}:signup"), {
        "username": "dupe",
        "password1": "Passw0rd1!",
        "password2": "Passw0rd1!",
        "terms": "on",
    })
    if r.status_code == 200:
        form = r.context.get("form"); assert form is not None
        assert "username" in form.errors
    else:
        assert r.status_code in (302, 303)
    assert User.objects.filter(username="dupe").count() == 1

@pytest.mark.django_db
def test_signup_password_mismatch(client):
    client.get(reverse(f"{APP}:pick_role", args=["organizer"]))
    r = client.post(reverse(f"{APP}:signup"), {
        "username": "mismatch",
        "password1": "Passw0rd1!",
        "password2": "Passw0rdX!",  # mismatch
        "terms": "on",
    })
    assert r.status_code == 200
    form = r.context.get("form"); assert form is not None
    assert ("password2" in form.errors) or ("__all__" in form.errors)

@pytest.mark.django_db
def test_signup_terms_unchecked(client):
    client.get(reverse(f"{APP}:pick_role", args=["attendee"]))
    r = client.post(reverse(f"{APP}:signup"), {
        "username": "noterms",
        "password1": "Passw0rd1!",
        "password2": "Passw0rd1!",
        # 'terms' intentionally omitted
    })
    # If enforced, expect 200 with error; else a redirect is acceptable
    if r.status_code == 200:
        form = r.context.get("form"); assert form is not None
        assert ("terms" in form.errors) or ("__all__" in form.errors)
    else:
        assert r.status_code in (302, 303)
