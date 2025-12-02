from django.urls import path
from . import views


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
    # Password reset
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # Profile
    path("profile/edit/", views.profile_edit, name="profile_edit"),
]
