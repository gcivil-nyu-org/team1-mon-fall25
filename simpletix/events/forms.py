from django import forms
from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "location",
            "formatted_address",
            "latitude",
            "longitude",
            "banner",
            "video",
        ]
        widgets = {
            "formatted_address": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }