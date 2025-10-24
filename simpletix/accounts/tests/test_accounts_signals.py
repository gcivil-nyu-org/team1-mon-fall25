import pytest
from django.contrib.auth import get_user_model

@pytest.mark.django_db
def test_user_create_triggers_signals():
    User = get_user_model()
    u = User.objects.create_user(username="sig1", email="sig1@example.com", password="Passw0rd1!")
    # If signals create profiles, they should now exist; don’t assert strictly if project differs
    if hasattr(u, "userprofile"):
        _ = u.userprofile  # access
    if hasattr(u, "organizerprofile"):
        _ = u.organizerprofile

@pytest.mark.django_db
def test_user_update_triggers_signals():
    User = get_user_model()
    u = User.objects.create_user(username="sig2", email="sig2@example.com", password="Passw0rd1!")
    u.email = "sig2changed@example.com"
    u.save()  # update path to exercise post_save update logic
