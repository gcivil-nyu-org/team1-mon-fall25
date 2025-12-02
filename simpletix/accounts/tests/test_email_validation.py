import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.forms import SignupForm, OrganizerProfileForm
from accounts.models import OrganizerProfile


@pytest.mark.django_db
def test_signup_rejects_duplicate_email():
    User.objects.create_user(username="u1", password="x", email="a@example.com")

    form = SignupForm(
        data={
            "username": "u2",
            "email": "a@example.com",
            "password1": "pass12345",
            "password2": "pass12345",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.django_db
def test_profile_edit_rejects_duplicate_email():
    u2 = User.objects.create_user(username="u2", password="x", email="")

    profile2, _ = OrganizerProfile.objects.get_or_create(user=u2)

    form = OrganizerProfileForm(
        data={"contact_email": "a@example.com"},
        instance=profile2,
    )

    assert not form.is_valid()
    assert "contact_email" in form.errors


@pytest.mark.django_db
def test_cannot_remove_existing_email(monkeypatch, client):
    user = User.objects.create_user(username="u1", password="x", email="a@example.com")
    client.login(username="u1", password="x")

    profile, _ = OrganizerProfile.objects.get_or_create(user=user)

    resp = client.post(
        reverse("accounts:profile_edit"),
        {
            "full_name": profile.full_name,
            "contact_email": "",  # trying to remove email
            "phone": "",
        },
    )

    assert "You cannot remove your email" in resp.content.decode()
    assert User.objects.get(username="u1").email == "a@example.com"


@pytest.mark.django_db
def test_profile_edit_prefills_existing_email(client):
    user = User.objects.create_user(username="u1", password="x", email="a@example.com")
    client.login(username="u1", password="x")
    OrganizerProfile.objects.create(user=user, contact_email="a@example.com")

    resp = client.get(reverse("accounts:profile_edit"))
    html = resp.content.decode()

    # field value should be in the HTML
    assert 'value="a@example.com"' in html
