from django import forms

from tickets.models import TicketInfo
from .models import Order


class OrderForm(forms.ModelForm):
    ticket_info = forms.ModelChoiceField(
        queryset=TicketInfo.objects.none(),
        label="Select Ticket Type",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    quantity = forms.IntegerField(
        label="Quantity",
        initial=1,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "id": "id_quantity",  # For JavaScript
                "min": "1",
                # Set a default max. JS will update this.
                "max": "1",  # A sensible default, will be overridden.
            }
        ),
    )

    class Meta:
        model = Order
        fields = ["ticket_info", "quantity", "full_name", "email", "phone"]
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
        preselect_ticket_category_id = kwargs.pop("preselect_ticket_category_id", None)
        super().__init__(*args, **kwargs)

        if event:
            # Only include tickets for this event with availability > 0.
            available = TicketInfo.objects.filter(event=event, availability__gt=0)
            self.fields["ticket_info"].queryset = available

            # Pretty dropdown labels
            self.fields["ticket_info"].label_from_instance = lambda obj: (
                f"{obj.get_category_display()} (${obj.price}) - "
                f"{obj.availability} available"
            )

            # Handle preselected ticket category field default
            selected_ticket = available.filter(id=preselect_ticket_category_id).first()

            if selected_ticket:
                self.initial["ticket_info"] = selected_ticket.id
                max_availability = selected_ticket.availability
            else:
                max_availability = (
                    available.first().availability if available.exists() else 0
                )

            self.fields["quantity"].widget.attrs["max"] = max_availability
            self.fields["quantity"].max_value = max_availability

    def clean(self):
        """
        Custom validation to ensure quantity does not exceed availability
        for the selected ticket_info.
        """
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        ticket_info = cleaned_data.get("ticket_info")

        # Only run validation if both fields are present
        if ticket_info and quantity:
            if quantity > ticket_info.availability:
                # This adds an error to the 'quantity' field specifically
                t_a = ticket_info.availability
                self.add_error(
                    "quantity",
                    f"There are only {t_a} tickets of this type available.",
                )

        return cleaned_data
