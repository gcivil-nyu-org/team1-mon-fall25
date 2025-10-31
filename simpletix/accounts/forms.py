# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from io import BytesIO
from PIL import Image, ImageOps  # for EXIF orientation fix

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap styling
        for name in ["username", "password1", "password2"]:
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
