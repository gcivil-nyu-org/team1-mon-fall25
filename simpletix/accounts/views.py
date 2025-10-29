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

from .forms import OrganizerProfileForm, SignupForm
from .models import OrganizerProfile, UserProfile

ALLOWED_ROLES = {"organizer", "attendee"}  # guest handled separately


class GetStartedView(TemplateView):
    template_name = "accounts/start.html"


# ---------- Role-aware redirects ----------
def _role_default_redirect(request, role: str):
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
    Login view that remembers intended role and redirects accordingly.
    If the requested role doesn't match the stored role, we ignore the
    request and take the user to their stored role's destination.
    """

    template_name = "accounts/login.html"

    def form_valid(self, form):
        # Persist chosen role hint (from hub) so templates can read it
        role = self.request.POST.get("role") or self.request.GET.get("role")
        if role:
            self.request.session["desired_role"] = role
        # Always clear guest on successful login
        self.request.session.pop("guest", None)
        return super().form_valid(form)

    def get_success_url(self):
        # Respect a safe ?next=
        next_url = self.get_redirect_url()
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}
        ):
            return next_url

        # Compare requested role vs stored role on the user profile
        requested = (
            self.request.POST.get("role")
            or self.request.GET.get("role")
            or self.request.session.get("desired_role")
            or "attendee"
        ).lower()

        stored = getattr(
            getattr(self.request.user, "uprofile", None), "role", "attendee"
        )

        if requested != stored:
            msg = (
                f"You’re signed up as {stored.title()}. "
                f"Showing the {stored.title()} view."
            )
            messages.info(self.request, msg)
            return _role_default_redirect(self.request, stored)

        return _role_default_redirect(self.request, stored)


# ---------- Entry points ----------
def pick_role(request, role: str):
    role = (role or "").lower()
    if role not in ALLOWED_ROLES:
        messages.error(request, "Invalid choice. Please pick Organizer or Attendee.")
        return redirect("accounts:start")

    request.session["desired_role"] = role

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

            # Ensure both profiles exist
            OrganizerProfile.objects.get_or_create(user=user)
            uprof, _ = UserProfile.objects.get_or_create(user=user)

            # Determine intended role from request/session; default attendee
            selected_role = (
                request.POST.get("role")
                or request.GET.get("role")
                or request.session.get("desired_role")
                or "attendee"
            ).lower()
            if selected_role not in ALLOWED_ROLES:
                selected_role = "attendee"

            # Store the role on the persistent profile
            uprof.role = selected_role
            uprof.save()

            # Log in, clear guest, keep the hint for templates
            auth_login(request, user)
            request.session.pop("guest", None)
            request.session["desired_role"] = selected_role

            messages.success(request, "Account created. Welcome to SimpleTix!")

            # Redirect preference: ?next= if safe, else role default
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(_role_default_redirect(request, selected_role))
    else:
        form = SignupForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


# ---------- (Optional) image util ----------
def _to_jpeg_rgb(uploaded_file) -> InMemoryUploadedFile:
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
            form.save()
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
    request.session.pop("guest", None)
    request.session.pop("desired_role", None)
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/"))


# ---------- Hub ----------
def start(request):
    for _ in messages.get_messages(request):
        pass
    return render(request, "accounts/start.html")
