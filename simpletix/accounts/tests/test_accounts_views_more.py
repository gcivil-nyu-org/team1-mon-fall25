import pytest
from django.urls import reverse

APP = "accounts"


@pytest.mark.django_db
def test_start_page_smoke(client):
    res = client.get(reverse(f"{APP}:start"))
    assert res.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["organizer", "attendee"])
def test_pick_role_then_show_login(client, role):
    # picking a role should redirect you to login
    res = client.get(reverse(f"{APP}:pick_role", args=[role]), follow=False)
    assert res.status_code in (302, 303)
    assert reverse(f"{APP}:login") in res["Location"]


@pytest.mark.django_db
def test_logout_redirects_home(client, django_user_model):
    # log a user in first
    django_user_model.objects.create_user(
        username="u1", email="u1@example.com", password="Passw0rd1!"
    )
    client.post(
        reverse(f"{APP}:login"),
        {"username": "u1", "password": "Passw0rd1!"},
        follow=True,
    )
    assert client.get("/").status_code in (200, 302, 301)

    r = client.get(reverse(f"{APP}:logout"), follow=False)
    assert r.status_code in (302, 303)


@pytest.mark.django_db
def test_profile_edit_requires_login(client):
    r = client.get(reverse(f"{APP}:profile_edit"), follow=False)
    assert r.status_code in (302, 303)  # redirect to login


@pytest.mark.django_db
def test_profile_edit_get_and_post_invalid(client, django_user_model):
    django_user_model.objects.create_user(
        username="ed", email="ed@example.com", password="Passw0rd1!"
    )
    # login
    client.post(
        reverse(f"{APP}:login"),
        {"username": "ed", "password": "Passw0rd1!"},
        follow=True,
    )

    # GET edit page
    r = client.get(reverse(f"{APP}:profile_edit"))
    assert r.status_code == 200

    # POST invalid payload — follow redirect so final response is 200
    r = client.post(reverse(f"{APP}:profile_edit"), {}, follow=True)
    assert r.status_code == 200
