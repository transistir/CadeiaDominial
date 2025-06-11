from django import forms
from .models import TIs

class TIsForm(forms.ModelForm):
    class Meta:
        model = TIs
        fields = ['nome', 'codigo', 'etnia']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'etnia': forms.TextInput(attrs={'class': 'form-control'}),
        } 