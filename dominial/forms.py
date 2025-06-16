from django import forms
from .models import TIs, Imovel, Pessoas, TerraIndigenaReferencia, Cartorios, Alteracoes

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
        queryset=Pessoas.objects.all().order_by('nome'),
        required=True,
        label='Proprietário',
        widget=forms.Select(attrs={'class': 'form-control'})
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

class AlteracaoForm(forms.ModelForm):
    class Meta:
        model = Alteracoes
        fields = [
            'tipo_alteracao_id', 'cartorio', 'livro', 'folha', 'data_alteracao',
            'registro_tipo', 'averbacao_tipo', 'titulo', 'cartorio_origem',
            'livro_origem', 'folha_origem', 'data_origem', 'transmitente',
            'adquirente', 'valor_transacao', 'area', 'observacoes'
        ]
        widgets = {
            'tipo_alteracao_id': forms.Select(attrs={'class': 'form-control'}),
            'cartorio': forms.Select(attrs={'class': 'form-control'}),
            'livro': forms.TextInput(attrs={'class': 'form-control'}),
            'folha': forms.TextInput(attrs={'class': 'form-control'}),
            'data_alteracao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'registro_tipo': forms.Select(attrs={'class': 'form-control'}),
            'averbacao_tipo': forms.Select(attrs={'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'cartorio_origem': forms.Select(attrs={'class': 'form-control'}),
            'livro_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'folha_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'data_origem': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'transmitente': forms.Select(attrs={'class': 'form-control'}),
            'adquirente': forms.Select(attrs={'class': 'form-control'}),
            'valor_transacao': forms.NumberInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        } 