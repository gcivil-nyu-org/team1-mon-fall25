# accounts/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView

from .forms import SignupForm, OrganizerProfileForm
from .models import OrganizerProfile, UserProfile


ALLOWED_ROLES = {"organizer", "attendee"}  # guest handled separately


def _sync_session_role_from_user(request):
    """
    Some templates still look at session['desired_role'].
    After a real login, we want that value to reflect the *actual* stored role.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return
    prof = getattr(user, "uprofile", None)
    real_role = getattr(prof, "role", None) or "attendee"
    request.session["desired_role"] = real_role


class GetStartedView(TemplateView):
    template_name = "accounts/start.html"


def _role_default_redirect(request, role: str):
    role = (role or "").lower()
    if role == "organizer":
        try:
            return reverse("organizer:dashboard")
        except Exception:
            try:
                return reverse("events:event_list")
            except Exception:
                return "/"
    try:
        return reverse("events:event_list")
    except Exception:
        return "/"


class RoleLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        # if someone is already logged in in this session, start clean
        if self.request.user.is_authenticated:
            auth_logout(self.request)

        resp = super().form_valid(form)

        # drop guest flags
        self.request.session.pop("guest", None)

        # 1) if request had an explicit role (?role=organizer), keep that
        explicit_role = (self.request.GET.get("role") or "").lower()
        if explicit_role in {"organizer", "attendee"}:
            self.request.session["desired_role"] = explicit_role
        else:
            # 2) otherwise sync from DB
            _sync_session_role_from_user(self.request)

        # rotate for safety
        self.request.session.cycle_key()
        return resp

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}
        ):
            return next_url

        stored = getattr(
            getattr(self.request.user, "uprofile", None), "role", "attendee"
        )
        return _role_default_redirect(self.request, stored)


def pick_role(request, role: str):
    role = (role or "").lower()
    if role not in ALLOWED_ROLES:
        messages.error(request, "Invalid choice. Please pick Organizer or Attendee.")
        return redirect("accounts:start")

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
    if request.method == "POST":
        if request.user.is_authenticated:
            auth_logout(request)

        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()

            OrganizerProfile.objects.get_or_create(user=user)
            uprof, _ = UserProfile.objects.get_or_create(user=user)

            selected_role = (
                request.POST.get("role")
                or request.GET.get("role")
                or request.session.get("desired_role")
                or "attendee"
            )
            selected_role = selected_role.lower()
            if selected_role not in ALLOWED_ROLES:
                selected_role = "attendee"

            uprof.role = selected_role
            uprof.save()

            auth_login(request, user)

            # clean guest BUT keep role from DB
            request.session.pop("guest", None)
            _sync_session_role_from_user(request)
            request.session.cycle_key()

            messages.success(request, "Account created. Welcome to SimpleTix!")

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


def logout_then_home(request):
    auth_logout(request)
    request.session.pop("guest", None)
    # after logout we can drop role as well
    request.session.pop("desired_role", None)
    request.session.cycle_key()
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/"))


def start(request):
    for _ in messages.get_messages(request):
        pass
    return render(request, "accounts/start.html")
