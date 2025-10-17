from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

app_name = "accounts"

urlpatterns = [
    path("start/", views.start, name="start"),
    path("signup/", views.signup, name="signup"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", views.logout_then_home, name="logout"),
        # New: Auth Hub + role pick + guest entry
    path("start/", views.GetStartedView.as_view(), name="start"),
    path("pick/<str:role>/", views.pick_role, name="pick_role"),
    path("guest/", views.guest_entry, name="guest_entry"),
]

