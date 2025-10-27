from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views


app_name = "accounts"

urlpatterns = [
    # Auth hub
    path("start/", views.GetStartedView.as_view(), name="start"),
    path("pick/<str:role>/", views.pick_role, name="pick_role"),
    path("guest/", views.guest_entry, name="guest_entry"),
    # Auth
    path("login/", views.RoleLoginView.as_view(), name="login"),  # <-- use custom view
    path("signup/", views.signup, name="signup"),
    path("logout/", views.logout_then_home, name="logout"),
    # Profile
    path("profile/edit/", views.profile_edit, name="profile_edit"),
]
