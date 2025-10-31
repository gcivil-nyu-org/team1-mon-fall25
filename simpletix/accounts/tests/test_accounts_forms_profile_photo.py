import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from accounts.forms import OrganizerProfileForm
from accounts.models import OrganizerProfile
from PIL import Image

pytestmark = pytest.mark.django_db


def make_png_bytes(size=(10, 10), mode="RGBA"):
    """Create an in-memory PNG image and return bytes."""
    img = Image.new(mode, size, (255, 0, 0, 128) if "A" in mode else (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_invalid_bytes():
    return b"not-an-image-at-all"


def _make_user_with_org_profile(username="puser"):
    User = get_user_model()
    u = User.objects.create_user(username=username, password="Passw0rd1!")
    op = OrganizerProfile.objects.create(user=u)
    return u, op


def test_profile_photo_png_alpha_normalized_to_jpeg_and_saved(tmp_path, settings):
    # Ensure MEDIA_ROOT is writable for the test save
    settings.MEDIA_ROOT = tmp_path

    u, op = _make_user_with_org_profile("okpng")
    png_bytes = make_png_bytes(mode="RGBA")  # has alpha → should be converted to RGB
    f = SimpleUploadedFile("avatar.png", png_bytes, content_type="image/png")

    form = OrganizerProfileForm(
        data={"full_name": "A", "contact_email": "a@example.com", "phone": "123"},
        files={"profile_photo": f},
        instance=op,
    )
    assert form.is_valid(), form.errors
    saved = form.save()  # triggers clean + save(storage)

    # The field should be populated and Django should have stored a .jpg
    assert saved.profile_photo
    # name endswith .jpg as returned by clean_profile_photo
    assert saved.profile_photo.name.lower().endswith(".jpg")


def test_profile_photo_optional_no_file_keeps_none():
    u, op = _make_user_with_org_profile("nofile")
    form = OrganizerProfileForm(
        data={"full_name": "", "contact_email": "", "phone": ""},
        files={},  # no upload
        instance=op,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    assert not saved.profile_photo  # remains empty/None
