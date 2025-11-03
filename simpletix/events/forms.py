from django import forms
from .models import Event


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
            "video"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "formatted_address": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }
