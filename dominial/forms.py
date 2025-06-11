from django import forms
from .models import TIs, Imovel, Pessoas, TerraIndigenaReferencia

class TIsForm(forms.ModelForm):
    terra_referencia = forms.ModelChoiceField(
        queryset=TerraIndigenaReferencia.objects.all().order_by('nome'),
        required=True,
        label='Terra Indígena',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = TIs
        fields = ['terra_referencia']
        widgets = {
            'terra_referencia': forms.Select(attrs={'class': 'form-control'}),
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