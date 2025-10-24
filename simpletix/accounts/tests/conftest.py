import pytest
from django.contrib.auth import get_user_model

@pytest.fixture
def User():
    return get_user_model()

@pytest.fixture
def organizer_user(db, User):
    # Default Django User requires username; 
    return User.objects.create_user(
        username="orguser",
        email="org@example.com",
        password="Passw0rd1!",
    )

@pytest.fixture
def attendee_user(db, User):
    return User.objects.create_user(
        username="attuser",
        email="att@example.com",
        password="Passw0rd1!",
    )
