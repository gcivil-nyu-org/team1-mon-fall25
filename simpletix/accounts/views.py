# accounts/views.py
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from PIL import Image, ImageOps

from .forms import SignupForm, OrganizerProfileForm
from .models import OrganizerProfile, UserProfile  # role profile


ALLOWED_ROLES = {"organizer", "attendee"}  # guest handled separately


class GetStartedView(TemplateView):
    template_name = "accounts/start.html"


# ---------- Role-aware redirects ----------
def _role_default_redirect(request, role: str):
    """
    Return a URL (string) to redirect to for a given role.
    LoginView.get_success_url expects a URL, not an HttpResponse.
    """
    role = (role or "").lower()
    if role == "organizer":
        # Try organizer dashboard; fall back to events list; then root.
        try:
            return reverse("organizer:dashboard")
        except Exception:
            try:
                return reverse("events:event_list")
            except Exception:
                return "/"
    # attendee or unknown -> events list (or root)
    try:
        return reverse("events:event_list")
    except Exception:
        return "/"


class RoleLoginView(auth_views.LoginView):
    """
    Hardened login:
    - If a user is already authenticated in this session, log them out first.
    - After successful login: clear guest / desired_role hints and rotate the session key.
    - Redirect based on the user's persisted role (never the session-picked hint).
    """

    template_name = "accounts/login.html"

    def form_valid(self, form):
        # Guard: avoid cross-role contamination in a shared browser session
        if self.request.user.is_authenticated:
            auth_logout(self.request)

        # Let Django authenticate & attach the user to the session
        response = super().form_valid(form)

        # Clean session hints and rotate key
        self.request.session.pop("guest", None)
        self.request.session.pop("desired_role", None)
        self.request.session.cycle_key()

        return response

    def get_success_url(self):
        # Respect a safe ?next=
        next_url = self.get_redirect_url()
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}
        ):
            return next_url

        # Derive role strictly from DB-backed profile
        stored = getattr(
            getattr(self.request.user, "uprofile", None), "role", "attendee"
        )
        return _role_default_redirect(self.request, stored)


# ---------- Entry points ----------
def pick_role(request, role: str):
    """
    Store a role hint ONLY for anonymous users.
    Authenticated users should always follow their persisted role.
    """
    role = (role or "").lower()
    if role not in ALLOWED_ROLES:
        messages.error(request, "Invalid choice. Please pick Organizer or Attendee.")
        return redirect("accounts:start")

    # Only store a hint for guests/anonymous
    if not request.user.is_authenticated:
        request.session["desired_role"] = role
        request.session.cycle_key()

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
    """
    Create a user, persist chosen role on the profile, and log in safely:
    - logout any pre-existing authenticated user in this session
    - clear guest/desired_role hints and rotate the key after login
    """
    if request.method == "POST":
        # If someone is already authenticated on this session, reset it first
        if request.user.is_authenticated:
            auth_logout(request)

        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Ensure both profiles exist
            OrganizerProfile.objects.get_or_create(user=user)
            uprof, _ = UserProfile.objects.get_or_create(user=user)

            # Determine intended role from request/session; default attendee
            selected_role = (
                request.POST.get("role")
                or request.GET.get("role")
                or request.session.get("desired_role")
                or "attendee"
            )
            selected_role = selected_role.lower()
            if selected_role not in ALLOWED_ROLES:
                selected_role = "attendee"

            # Persist the role
            uprof.role = selected_role
            uprof.save()

            # Log in the new user
            auth_login(request, user)

            # Clean hints & rotate session key
            request.session.pop("guest", None)
            request.session.pop("desired_role", None)
            request.session.cycle_key()

            messages.success(request, "Account created. Welcome to SimpleTix!")

            # Redirect preference: safe ?next= else role default
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect(_role_default_redirect(request, selected_role))
    else:
        form = SignupForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


# ---------- (Optional) image util; kept for future use ----------
def _to_jpeg_rgb(uploaded_file) -> InMemoryUploadedFile:
    """
    Convert an uploaded image (possibly RGBA/Palette) to RGB JPEG in-memory.
    Returns an InMemoryUploadedFile suitable for assigning to an ImageField.
    """
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
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


# ---------- Profile ----------
@login_required
def profile_edit(request):
    profile, _ = OrganizerProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = OrganizerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()  # OrganizerProfileForm normalizes images
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


# ---------- Logout ----------
def logout_then_home(request):
    auth_logout(request)
    # Clean session flags on logout and rotate
    request.session.pop("guest", None)
    request.session.pop("desired_role", None)
    request.session.cycle_key()
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/"))


# ---------- Hub ----------
def start(request):
    # Clear any queued messages so the hub looks clean on refresh
    for _ in messages.get_messages(request):
        pass
    return render(request, "accounts/start.html")
