"""Forms for the claim module."""
from datetime import datetime

from django import forms

from .models import MAX_PORTIONS_PER_CLAIM, NOTE_MAX_LENGTH
from .utils import build_pickup_slots, format_datetime


class ClaimForm(forms.Form):
    """Form a recipient fills in to claim a donation."""

    portions = forms.IntegerField(
        label="Jumlah porsi",
        min_value=1,
        error_messages={
            "required": "Isi jumlah porsi.",
            "invalid": "Jumlah porsi harus berupa angka.",
            "min_value": "Jumlah porsi minimal 1.",
        },
        widget=forms.NumberInput(
            attrs={
                "class": "form-control claim-input",
                "min": 1,
                "inputmode": "numeric",
                "data-portion-input": "",
            }
        ),
    )
    pickup_time = forms.ChoiceField(
        label="Waktu ambil",
        error_messages={
            "required": "Pilih waktu ambil.",
            "invalid_choice": "Pilih waktu ambil yang tersedia.",
        },
        widget=forms.Select(attrs={"class": "form-select claim-input"}),
    )
    note = forms.CharField(
        label="Catatan untuk donor",
        required=False,
        max_length=NOTE_MAX_LENGTH,
        error_messages={"max_length": f"Catatan maksimal {NOTE_MAX_LENGTH} huruf."},
        widget=forms.TextInput(
            attrs={
                "class": "form-control claim-input",
                "maxlength": NOTE_MAX_LENGTH,
                "autocomplete": "off",
                "placeholder": "Contoh: Saya ambil bersama satu teman.",
                "data-char-counter": "#note-counter",
            }
        ),
    )

    def __init__(self, *args, donation, remaining_portions, **kwargs):
        super().__init__(*args, **kwargs)
        self.remaining_portions = remaining_portions
        self.max_portions = max(min(MAX_PORTIONS_PER_CLAIM, remaining_portions), 1)

        portions_field = self.fields["portions"]
        portions_field.initial = 1
        portions_field.widget.attrs["max"] = self.max_portions

        # Slots run from now (or when the food becomes available) until the deadline.
        slots = build_pickup_slots(donation.pickup_deadline, start=donation.pickup_start)
        self.fields["pickup_time"].choices = [
            (slot.isoformat(), format_datetime(slot)) for slot in slots
        ]
        if slots:
            self.fields["pickup_time"].initial = slots[0].isoformat()

    def clean_portions(self):
        """Validate the portions against the per-claim cap and remaining stock."""
        value = self.cleaned_data["portions"]
        if value > MAX_PORTIONS_PER_CLAIM:
            raise forms.ValidationError(f"Maksimal {MAX_PORTIONS_PER_CLAIM} porsi per klaim.")
        if value > self.remaining_portions:
            raise forms.ValidationError(f"Porsi yang tersisa hanya {self.remaining_portions}.")
        return value

    def clean_pickup_time(self):
        """Convert the selected slot (ISO string) to an aware datetime."""
        return datetime.fromisoformat(self.cleaned_data["pickup_time"])