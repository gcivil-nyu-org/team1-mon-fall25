from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from decimal import Decimal

from events.models import Event
from .models import TicketInfo


class TicketInfoForm(forms.ModelForm):
    """A custom form for the formset to control the name widget."""

    price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0.5",  # <-- Client-side (browser) validation
            }
        ),
    )

    availability = forms.IntegerField(
        min_value=0,  # <-- Server-side validation
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",  # <-- Client-side (browser) validation
            }
        ),
    )

    class Meta:
        model = TicketInfo
        fields = ["category", "is_active", "price", "availability"]
        # The 'name' field is hidden; its value will be set in the view.
        widgets = {
            "category": forms.HiddenInput(),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        """
        Custom validation for active tickets.
        """
        cleaned_data = super().clean()
        is_active = cleaned_data.get("is_active")
        price = cleaned_data.get("price")
        availability = cleaned_data.get("availability")

        if is_active:
            # If the ticket is active, price and availability are required.
            if price is None:
                self.add_error("price", "Price is required for active tickets.")
            elif price < Decimal("0.5"):
                self.add_error("price", "Price must be at least $0.50.")
            if availability is None:
                self.add_error(
                    "availability", "Availability is required for active tickets."
                )
        else:
            # If the ticket is NOT active, set price/availability to 0
            # so they don't clog up the form but save safely.
            cleaned_data["price"] = Decimal("0.0")
            cleaned_data["availability"] = 0

        return cleaned_data


class BaseTicketFormSet(BaseInlineFormSet):
    def clean(self):
        """
        Checks that at least one ticket type is active.
        """
        super().clean()

        if not self.forms:
            return

        at_least_one_active = False
        for form in self.forms:
            if form.cleaned_data and form.cleaned_data.get("is_active"):
                at_least_one_active = True
                break  # Found one, no need to check the rest

        if not at_least_one_active:
            # This error will appear at the top of the formset
            raise ValidationError("You must enable at least one ticket type.")


TicketFormSet = inlineformset_factory(
    Event,
    TicketInfo,
    form=TicketInfoForm,
    formset=BaseTicketFormSet,
    extra=3,
    min_num=3,
    max_num=3,
    can_delete=False,
)
