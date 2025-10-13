from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image  

from .models import OrganizerProfile


class SignupForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text="Pick a unique username.",
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
        fields = ("username", "password1", "password2")


class OrganizerProfileForm(forms.ModelForm):
    class Meta:
        model = OrganizerProfile
        fields = ["full_name", "contact_email", "phone", "profile_photo"]

    def clean_profile_photo(self):
        """
        Validate size/type. If provided, verify it's a real image and
        re-encode to strip EXIF/metadata (keeps things small and safe).
        """
        file = self.cleaned_data.get("profile_photo")
        if not file:
            return file  # optional

        # 1) Size limit (2MB)
        max_bytes = 2 * 1024 * 1024
        if getattr(file, "size", 0) and file.size > max_bytes:
            raise ValidationError("Please upload an image smaller than 2MB.")

        # 2) Basic content-type allowlist (if available)
        ctype = getattr(file, "content_type", None)
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if ctype and ctype not in allowed:
            raise ValidationError("Only JPEG, PNG, or WebP images are allowed.")

        # 3) Verify it's actually an image
        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()  # quick integrity check
        except Exception:
            raise ValidationError("That file is not a valid image.")

        # 4) Re-open for processing (verify() closes the underlying parser)
        file.seek(0)
        img = Image.open(file)

        # Convert to RGB to normalize (avoids mode issues on save)
        # If you prefer to preserve transparency for PNG/WebP, you can branch here.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # 5) Re-encode to strip EXIF/metadata
        # Default to JPEG for good compatibility/size
        buf = BytesIO()
        img.save(buf, format="JPEG", optimize=True, quality=85)
        buf.seek(0)

        # 6) Return a fresh Django file object (with .jpg extension)
        base_name = (getattr(file, "name", "profile").rsplit(".", 1)[0] or "profile").replace(" ", "_")
        new_name = f"{base_name}.jpg"
        return ContentFile(buf.read(), name=new_name)
