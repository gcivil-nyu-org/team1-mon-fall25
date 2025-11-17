from django import forms
from .models import Event
from django.utils import timezone


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "date",
            "time",
            "location",
            "formatted_address",
            "latitude",
            "longitude",
            "banner",
            "video",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "formatted_address": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")

        if date and date < timezone.localdate():
            self.add_error("date", "Event date cannot be in the past.")

        return cleaned_data
