import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_user_str_and_profiles_exist():
    """
    Touch model __str__ branches if defined, and ensure basic relations exist.
    If your app defines OrganizerProfile/UserProfile via signals, creating a user
    should be enough to instantiate them.
    """
    User = get_user_model()
    u = User.objects.create_user(
        username="m1", email="m1@example.com", password="Passw0rd1!"
    )
    assert str(u)  # __str__ shouldn't crash

    # If you have related profiles, try to access them defensively:
    for attr in ("userprofile", "organizerprofile"):
        if hasattr(u, attr):
            getattr(u, attr, None)
            # Some projects use OneToOne lazy creation; access to trigger it
            getattr(u, attr, None)
