from django import forms
from .models import Event, Ticket
from django.forms import inlineformset_factory

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'time', 'location', 'banner', 'video']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
        }

TicketFormSet = inlineformset_factory(
    Event,
    Ticket,
    fields=('category', 'price', 'availability'),
    extra=1,
    can_delete=True
)
