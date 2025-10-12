from django.contrib import messages
from django.contrib.auth import login as auth_login, logout 
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import SignupForm, OrganizerProfileForm
from .models import OrganizerProfile

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

            # Prefer explicit next param; otherwise go home
            next_url = request.GET.get("next") or request.POST.get("next")
            # If your home is named route "home:index", keep it; otherwise use "/"
            return redirect(next_url or "/")
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
    """Log out and go to the homepage (no banner)."""
    logout(request)
    return redirect("simpletix:index")

def start(request):
    for _ in messages.get_messages(request):
        pass
    return render(request, "accounts/start.html")

