from django import forms
from ..models import TIs


class TIsForm(forms.ModelForm):
    nome = forms.CharField(
        label='Nome da Terra Indígena',
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Terra Indígena Yanomami'
        })
    )
    
    codigo = forms.CharField(
        label='Código',
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: TI001'
        })
    )
    
    etnia = forms.CharField(
        label='Etnia',
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Yanomami'
        })
    )
    
    estado = forms.MultipleChoiceField(
        label='Estados',
        choices=[
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
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'estado-checkboxes'
        }),
        help_text='Selecione todos os estados onde a Terra Indígena está localizada'
    )
    
    area = forms.DecimalField(
        label='Área (hectares)',
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 1000.50',
            'step': '0.01',
            'min': '0'
        })
    )

    class Meta:
        model = TIs
        fields = ['nome', 'codigo', 'etnia', 'estado', 'area']
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            # Verificar se já existe uma TI com este código
            if TIs.objects.filter(codigo=codigo).exists():
                raise forms.ValidationError('Já existe uma Terra Indígena com este código.')
        return codigo
    
    def clean_estado(self):
        estados = self.cleaned_data.get('estado')
        if not estados:
            raise forms.ValidationError('Selecione pelo menos um estado.')
        return estados
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Converter lista de estados para string separada por vírgula
        estados = self.cleaned_data.get('estado', [])
        if estados:
            instance.estado = ', '.join(estados)
        if commit:
            instance.save()
        return instance 