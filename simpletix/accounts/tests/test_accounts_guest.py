import pytest
from django.urls import reverse

APP = "accounts"

# Project-specific knobs — set these once:
GUEST_METHOD = "get"                 # "get" or "post" depending on the guest_entry view
RESTRICTED_URL_NAME = f"{APP}:profile_edit"  # change if profile_edit isn't login_required
EXPECTS_SESSION_FLAG = False         # True if the guest_entry sets a flag in session
GUEST_SESSION_KEY = "is_guest"       # the flag key if set one

@pytest.mark.django_db
def test_guest_entry_is_accessible(client):
    """
    /accounts/guest/ is callable and leads to a public page; we don't enforce a specific target.
    """
    url = reverse(f"{APP}:guest_entry")
    res = getattr(client, GUEST_METHOD)(url, follow=True)
    assert res.status_code in (200, 302), "Guest entry should render or redirect successfully"

    # Optional: verify a session flag if your view sets one
    if EXPECTS_SESSION_FLAG:
        assert client.session.get(GUEST_SESSION_KEY) is True, (
            f"Expected session flag {GUEST_SESSION_KEY}=True after guest entry"
        )

    # Public page should remain browsable after guest entry
    start = client.get(reverse(f"{APP}:start"))
    assert start.status_code == 200

@pytest.mark.django_db
def test_guest_restricted_action_redirects_to_login(client, settings):
    """
    Anonymous/guest user hitting a restricted URL should be redirected to the login page with ?next=
    """
    restricted = reverse(RESTRICTED_URL_NAME)
    res = client.get(restricted, follow=False)
    assert res.status_code in (302, 303)

    location = res["Location"]

    # Normalize LOGIN_URL checks whether it's a path (e.g. "/accounts/login/")
    # or you can fall back to the named route.
    login_url_setting = getattr(settings, "LOGIN_URL", None)
    login_url_named = reverse(f"{APP}:login")

    ok_login_target = False
    if login_url_setting:
        # If LOGIN_URL is a named route like "accounts:login", reverse it safely
        try:
            login_url_from_setting = reverse(login_url_setting)
        except Exception:
            login_url_from_setting = login_url_setting  # assume it's already a path
        ok_login_target = (login_url_from_setting in location)
    # Also allow the named route explicitly
    ok_login_target = ok_login_target or (login_url_named in location)

    assert ok_login_target, f"Expected redirect to login. Got: {location}"
    assert "next=" in location, "Expected ?next= param to preserve intended destination"

@pytest.mark.django_db
def test_guest_restricted_post_redirects_to_login(client, settings):
    """
    Cover the POST branch too (often different view decorators/middleware).
    """
    restricted = reverse(RESTRICTED_URL_NAME)
    res = client.post(restricted, {}, follow=False)
    assert res.status_code in (302, 303)
    assert "next=" in res["Location"]

@pytest.mark.django_db
def test_guest_entry_then_restricted_flow_again(client, settings):
    """
    Enter as guest first, then try restricted again — behavior should be the same (redirect to login).
    """
    getattr(client, GUEST_METHOD)(reverse(f"{APP}:guest_entry")),  
    restricted = reverse(RESTRICTED_URL_NAME)
    res = client.get(restricted, follow=False)
    assert res.status_code in (302, 303)
    assert "next=" in res["Location"]
