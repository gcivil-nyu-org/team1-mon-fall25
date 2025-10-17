# accounts/views.py
from io import BytesIO
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.generic import TemplateView
from django.conf import settings
from PIL import Image, ImageOps
from .forms import SignupForm, OrganizerProfileForm
from .models import OrganizerProfile


ALLOWED_ROLES = {"organizer", "attendee"}  # guest handled separately


class GetStartedView(TemplateView):
    template_name = "accounts/start.html"  # reuse your existing file


def pick_role(request, role: str):
    role = (role or "").lower()
    if role not in ALLOWED_ROLES:
        messages.error(request, "Invalid choice. Please pick Organizer or Attendee.")
        return redirect("accounts:start")

    # Remember what the user intended (optional, not used in templates now)
    request.session["desired_role"] = role

    # Send to your existing login page (signup is linked from there and from the hub)
    try:
        login_url = reverse("accounts:login")
    except NoReverseMatch:
        login_url = "/accounts/login/"

    return redirect(f"{login_url}?role={role}")


def guest_entry(request):
    request.session["guest"] = True
    messages.info(request, "You’re browsing as a guest. Sign up to save your activity.")
    return redirect(f"{reverse('events:event_list')}?guest=1")


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Ensure the profile exists for this user
            OrganizerProfile.objects.get_or_create(user=user)

            # Log in the new user
            auth_login(request, user)

            messages.success(request, "Account created. Welcome to SimpleTix!")

            next_url = request.GET.get("next") or request.POST.get("next")
            return redirect(next_url or "/")
    else:
        form = SignupForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


# ---------- Image utils ----------
def _to_jpeg_rgb(uploaded_file) -> InMemoryUploadedFile:
    """
    Convert an uploaded image (possibly RGBA/Palette) to RGB JPEG in-memory.
    Returns an InMemoryUploadedFile suitable for assigning to an ImageField.
    """
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)

    # Respect EXIF orientation if present
    img = ImageOps.exif_transpose(img)

    # JPEG can't store alpha/Palette; normalize to RGB
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)

    stem = Path(uploaded_file.name).stem or "avatar"
    out_name = f"{stem}.jpg"
    return InMemoryUploadedFile(
        file=buf,
        field_name="ImageField",
        name=out_name,
        content_type="image/jpeg",
        size=buf.getbuffer().nbytes,
        charset=None,
    )


@login_required
@login_required
def profile_edit(request):
    profile, _ = OrganizerProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = OrganizerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()  # cleaned_data already contains normalized JPEG
            messages.success(request, "Profile updated successfully.")
            next_url = request.POST.get("next") or request.GET.get("next") or "/"
            return redirect(next_url)
    else:
        form = OrganizerProfileForm(instance=profile)

    return render(
        request,
        "accounts/profile_edit.html",
        {"form": form, "next": request.GET.get("next", "/")},
    )


def logout_then_home(request):
    auth_logout(request)
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/"))


def start(request):
    # Clear any queued messages so the hub looks clean on refresh
    for _ in messages.get_messages(request):
        pass
    return render(request, "accounts/start.html")
