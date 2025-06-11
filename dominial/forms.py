from django import forms
from .models import TIs, Imovel, Pessoas

class TIsForm(forms.ModelForm):
    class Meta:
        model = TIs
        fields = ['nome', 'codigo', 'etnia']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'etnia': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ImovelForm(forms.ModelForm):
    class Meta:
        model = Imovel
        fields = ['nome', 'proprietario', 'matricula', 'sncr', 'sigef', 'descricao', 'observacoes']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'proprietario': forms.Select(attrs={'class': 'form-control'}),
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
            'sncr': forms.TextInput(attrs={'class': 'form-control'}),
            'sigef': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        } 