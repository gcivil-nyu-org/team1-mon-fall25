from django import forms

from tickets.models import TicketInfo
from .models import Order


class OrderForm(forms.ModelForm):
    ticket_info = forms.ModelChoiceField(
        queryset=TicketInfo.objects.none(),
        label="Select Ticket Type",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Order
        fields = ["ticket_info", "full_name", "email", "phone"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Your Full Name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "you@example.com"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(555) 123-4567"}
            ),
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        if event:
            # Only include tickets for this event with availability > 0.
            available = TicketInfo.objects.filter(event=event, availability__gt=0)
            self.fields["ticket_info"].queryset = available

            # Pretty dropdown labels, wrapped to stay under 88 chars.
            self.fields["ticket_info"].label_from_instance = lambda obj: (
                f"{obj.get_category_display()} (${obj.price}) - "
                f"{obj.availability} available"
            )
