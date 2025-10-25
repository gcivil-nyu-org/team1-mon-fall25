import pytest
from django.urls import reverse

APP = "accounts"


@pytest.mark.django_db
def test_organizer_login_success_flow(client, django_user_model):
    django_user_model.objects.create_user(username="orguser", password="Passw0rd1!")
    client.get(reverse(f"{APP}:pick_role", args=["organizer"]))
    res = client.post(
        reverse(f"{APP}:login"),
        {
            "username": "orguser",
            "password": "Passw0rd1!",
        },
        follow=True,
    )
    assert res.redirect_chain
    assert getattr(res.wsgi_request.user, "is_authenticated", False) is True


@pytest.mark.django_db
def test_attendee_login_success_flow(client, django_user_model):
    django_user_model.objects.create_user(username="attuser", password="Passw0rd1!")
    client.get(reverse(f"{APP}:pick_role", args=["attendee"]))
    res = client.post(
        reverse(f"{APP}:login"),
        {
            "username": "attuser",
            "password": "Passw0rd1!",
        },
        follow=True,
    )
    assert res.redirect_chain
    assert getattr(res.wsgi_request.user, "is_authenticated", False) is True


@pytest.mark.django_db
def test_organizer_signup_success_flow(client):
    client.get(reverse(f"{APP}:pick_role", args=["organizer"]))
    res = client.post(
        reverse(f"{APP}:signup"),
        {
            "username": "neworg",
            "password1": "Passw0rd1!",
            "password2": "Passw0rd1!",
            "terms": "on",  # keep if your form enforces it; harmless otherwise
        },
        follow=True,
    )
    assert res.redirect_chain
    assert getattr(res.wsgi_request.user, "is_authenticated", False) is True


@pytest.mark.django_db
def test_attendee_signup_success_flow(client):
    client.get(reverse(f"{APP}:pick_role", args=["attendee"]))
    res = client.post(
        reverse(f"{APP}:signup"),
        {
            "username": "newatt",
            "password1": "Passw0rd1!",
            "password2": "Passw0rd1!",
            "terms": "on",
        },
        follow=True,
    )
    assert res.redirect_chain
    assert getattr(res.wsgi_request.user, "is_authenticated", False) is True
