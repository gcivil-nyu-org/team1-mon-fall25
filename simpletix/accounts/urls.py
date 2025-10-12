from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, reverse_lazy

app_name = "accounts"

urlpatterns = [
    path("start/", views.start, name="start"),
    path("signup/", views.signup, name="signup"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", views.logout_then_home, name="logout"),
]

