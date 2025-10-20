from django import forms
from events.models import Event
from django.forms import inlineformset_factory

from .models import TicketInfo, Ticket


class TicketInfoForm(forms.ModelForm):
    """A custom form for the formset to control the name widget."""
    class Meta:
        model = TicketInfo
        fields = ['category', 'price', 'availability']
        # The 'name' field is hidden; its value will be set in the view.
        widgets = {
            'category': forms.HiddenInput(),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'availability': forms.NumberInput(attrs={'class': 'form-control'}),
        }

TicketFormSet = inlineformset_factory(
    Event,
    TicketInfo,
    form=TicketInfoForm,
    extra=3,
    min_num=3,
    max_num=3,
    can_delete=False
)

class OrderForm(forms.ModelForm):
    ticketInfo = forms.ModelChoiceField(
        queryset=TicketInfo.objects.none(), 
        label="Select Ticket Type",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Ticket
        fields = ["ticketInfo", "full_name", "email", "phone"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your Full Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "(555) 123-4567"}),
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        if event:
            # Filter the queryset to only include tickets for this event
            # with availability greater than zero.
            available_tickets = TicketInfo.objects.filter(event=event, availability__gt=0)
            self.fields['ticketInfo'].queryset = available_tickets
            
            # Customize the label for each choice in the dropdown
            self.fields['ticketInfo'].label_from_instance = lambda obj: (
                f"{obj.get_category_display()} (${obj.price}) - {obj.availability} available"
            )
