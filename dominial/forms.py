from django import forms
from .models import TIs, Imovel, Pessoas, TerraIndigenaReferencia, Cartorios
from dal import autocomplete

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
    proprietario = forms.ModelChoiceField(
        queryset=Pessoas.objects.all(),
        required=True,
        label='Proprietário',
        widget=autocomplete.ModelSelect2(url='pessoa-autocomplete')
    )

    estado = forms.ChoiceField(
        choices=[('', 'Selecione um estado')] + [
            ('AC', 'Acre'), ('AL', 'Alagoas'), ('AM', 'Amazonas'), ('AP', 'Amapá'),
            ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
            ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
            ('MG', 'Minas Gerais'), ('MS', 'Mato Grosso do Sul'), ('MT', 'Mato Grosso'),
            ('PA', 'Pará'), ('PB', 'Paraíba'), ('PE', 'Pernambuco'), ('PI', 'Piauí'),
            ('PR', 'Paraná'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
            ('RO', 'Rondônia'), ('RR', 'Roraima'), ('RS', 'Rio Grande do Sul'),
            ('SC', 'Santa Catarina'), ('SE', 'Sergipe'), ('SP', 'São Paulo'),
            ('TO', 'Tocantins')
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    cidade = forms.CharField(
        required=True,
        widget=forms.HiddenInput()
    )
    
    cartorio = forms.ModelChoiceField(
        queryset=Cartorios.objects.all(),
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Imovel
        fields = ['nome', 'proprietario', 'matricula', 'sncr', 'sigef', 'descricao', 'observacoes', 'estado', 'cidade', 'cartorio']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
            'sncr': forms.TextInput(attrs={'class': 'form-control'}),
            'sigef': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        } 