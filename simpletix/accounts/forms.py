from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import OrganizerProfile

class SignupForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text="Pick a unique username."
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Use a strong password (Django validators enforced)."
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2")


class OrganizerProfileForm(forms.ModelForm):
    class Meta:
        model = OrganizerProfile
        fields = ("full_name", "contact_email", "phone_number", "profile_photo")
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "contact_email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone_number": forms.TextInput(attrs={"placeholder": "+1 555 123 4567"}),
        }
