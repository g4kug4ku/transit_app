from django import forms
from .models import BentoReservation

class BentoReservationForm(forms.ModelForm):
    class Meta:
        model = BentoReservation
        fields = ['main_dish', 'rice', 'rice_weight']
