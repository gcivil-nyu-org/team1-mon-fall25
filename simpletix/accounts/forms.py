# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from io import BytesIO
import re
from PIL import Image, ImageOps
from .models import OrganizerProfile


class SignupForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text="Pick a unique username.",
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        help_text="We'll send password resets here.",
    )

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
        help_text="Use a strong password (Django validators enforced).",
    )

    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()

        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")

        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap styling
        for name in ["username", "email", "password1", "password2"]:
            self.fields[name].widget.attrs.update({"class": "form-control"})


class OrganizerProfileForm(forms.ModelForm):
    class Meta:
        model = OrganizerProfile
        fields = ["full_name", "contact_email", "phone", "profile_photo"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Your name"}
            ),
            "contact_email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "you@example.com"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(555) 123-4567"}
            ),
            "profile_photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_full_name(self):
        """
        Enforce a human-looking full name when provided:

        - If left blank, keep existing behavior (optional field).
        - If provided, must contain at least one alphabetic character.
        - Only allow letters, spaces, hyphens, apostrophes and periods.
        """
        full_name = (self.cleaned_data.get("full_name") or "").strip()

        # Preserve previous behavior: full_name is optional.
        # We only validate when the user actually enters something.
        if not full_name:
            return full_name

        # Require at least one alphabetic character
        if not re.search(r"[A-Za-z]", full_name):
            raise ValidationError("Full name must include at least one letter.")

        # Only allow safe character set
        allowed_pattern = r"^[A-Za-z\s\-\.'’]+$"
        if not re.match(allowed_pattern, full_name):
            raise ValidationError(
                "Full name can only contain letters, spaces, hyphens, "
                "apostrophes, and periods."
            )

        return full_name

    def clean_phone(self):
        """
        Validate phone numbers:

        - Optional: if left blank, keep existing behavior.
        - If provided, allow only digits, spaces, +, -, (, ).
        - Enforce a realistic digit length (7–15 digits).
        """
        phone = (self.cleaned_data.get("phone") or "").strip()

        # Phone is optional
        if not phone:
            return phone

        # Only allow digits and common phone punctuation
        allowed_pattern = r"^[0-9+\-\s()]+$"
        if not re.match(allowed_pattern, phone):
            raise ValidationError(
                "Phone number can only contain digits and the characters "
                "+, -, spaces, and parentheses."
            )

        # Count only the digits to validate length
        digit_count = sum(ch.isdigit() for ch in phone)
        if digit_count < 10 or digit_count > 10:
            raise ValidationError("Phone number is invalid")

        return phone

    def clean_profile_photo(self):
        """
        Validate and normalize the uploaded image:
        - Size < 2MB
        - Allow JPEG/PNG/WebP
        - Verify it's an image
        - Fix EXIF orientation, convert to RGB
        - Re-encode as JPEG (strips EXIF/metadata)
        """
        file = self.cleaned_data.get("profile_photo")
        if not file:
            return file  # optional

        # 1) Size limit (2MB)
        max_bytes = 2 * 1024 * 1024
        if getattr(file, "size", 0) and file.size > max_bytes:
            raise ValidationError("Please upload an image smaller than 2MB.")

        # 2) Content-type allowlist (if provided by the client)
        ctype = getattr(file, "content_type", None)
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if ctype and ctype not in allowed:
            raise ValidationError("Only JPEG, PNG, or WebP images are allowed.")

        # 3) Verify it's actually an image
        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()  # integrity check; closes parser state
        except Exception:
            raise ValidationError("That file is not a valid image.")

        # 4) Re-open for processing and normalize
        file.seek(0)
        img = Image.open(file)

        # Fix EXIF orientation (prevents rotated avatars)
        img = ImageOps.exif_transpose(img)

        # JPEG can't store alpha/palette; normalize to RGB
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 5) Re-encode as JPEG to strip metadata
        buf = BytesIO()
        img.save(buf, format="JPEG", optimize=True, quality=85)
        buf.seek(0)

        # 6) Wrap as Django file with .jpg extension
        base_name = (
            getattr(file, "name", "profile").rsplit(".", 1)[0] or "profile"
        ).replace(" ", "_")
        new_name = f"{base_name}.jpg"
        return ContentFile(buf.read(), name=new_name)

    def clean_contact_email(self):
        email = (self.cleaned_data.get("contact_email") or "").lower().strip()

        # Optional field — empty is allowed
        if not email:
            return ""

        # Check if another *User* already uses this email
        exists = (
            User.objects.filter(email=email).exclude(id=self.instance.user.id).exists()
        )
        if exists:
            raise ValidationError("This email is already used by another account.")

        return email
