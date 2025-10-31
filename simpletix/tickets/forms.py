from django import forms
from django.forms import inlineformset_factory

from events.models import Event
from .models import Ticket, TicketInfo


class TicketInfoForm(forms.ModelForm):
    """A custom form for the formset to control the name widget."""

    class Meta:
        model = TicketInfo
        fields = ["category", "price", "availability"]
        # The 'name' field is hidden; its value will be set in the view.
        widgets = {
            "category": forms.HiddenInput(),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "availability": forms.NumberInput(attrs={"class": "form-control"}),
        }


TicketFormSet = inlineformset_factory(
    Event,
    TicketInfo,
    form=TicketInfoForm,
    extra=3,
    min_num=3,
    max_num=3,
    can_delete=False,
)
