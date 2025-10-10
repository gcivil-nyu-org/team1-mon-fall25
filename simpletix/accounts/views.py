from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth import login as auth_login 

from .forms import SignupForm, OrganizerProfileForm
from .models import OrganizerProfile


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()    
            OrganizerProfile.objects.get_or_create(user=user)                
            auth_login(request, user)            
            messages.success(request, "Account created. Welcome to SimpleTix!")
            next_url = request.GET.get("next") or request.POST.get("next")
            # Redirect to Home by default (no forced profile edit)
            return redirect(next_url or "home:index")
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