from django import forms
from ..models import Imovel, Cartorios


class ImovelForm(forms.ModelForm):
    proprietario_nome = forms.CharField(
        label='Nome do Proprietário',
        required=False,  # Agora opcional, pois você vai validar manualmente depois
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_proprietario_nome'})
    )
    proprietario = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
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
    
    cidade = forms.ModelChoiceField(
        queryset=Cartorios.objects.values_list('cidade', 'cidade').distinct().order_by('cidade'),
        empty_label='Selecione uma cidade',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    cartorio = forms.ModelChoiceField(
        queryset=Cartorios.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Imovel
        fields = ['nome', 'matricula', 'observacoes']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        } 
    
    def clean(self):
        cleaned_data = super().clean()
        nome = cleaned_data.get('proprietario_nome')
        proprietario = cleaned_data.get('proprietario')

        # Se usuário digitou nome mas não selecionou uma pessoa existente
        if not proprietario:
            # Validação extra se quiser
            if not nome:
                raise forms.ValidationError('É obrigatório informar o nome do proprietário.')
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Preencher campos customizados
        instance = kwargs.get('instance')
        if instance:
            if instance.proprietario:
                self.fields['proprietario_nome'].initial = instance.proprietario.nome
            if hasattr(instance, 'cartorio') and instance.cartorio:
                self.fields['cartorio'].initial = instance.cartorio
            # Estado e cidade
            if hasattr(instance, 'cartorio') and instance.cartorio:
                if instance.cartorio.estado:
                    self.fields['estado'].initial = instance.cartorio.estado
                    # Filtrar cidades do estado
                    self.fields['cidade'].queryset = Cartorios.objects.filter(
                        estado=instance.cartorio.estado
                    ).values_list('cidade', 'cidade').distinct().order_by('cidade')
                if instance.cartorio.cidade:
                    self.fields['cidade'].initial = instance.cartorio.cidade
                    # Filtrar cartórios pela cidade
                    cartorios_cidade = Cartorios.objects.filter(
                        estado=instance.cartorio.estado,
                        cidade=instance.cartorio.cidade
                    ).order_by('nome')
                    self.fields['cartorio'].queryset = cartorios_cidade
        
        # Se há dados do POST (formulário com erro), filtrar cidades do estado
        if self.data:  # Se há dados do POST
            estado_post = self.data.get('estado')
            if estado_post:
                # Filtrar cidades do estado do POST
                self.fields['cidade'].queryset = Cartorios.objects.filter(
                    estado=estado_post
                ).values_list('cidade', 'cidade').distinct().order_by('cidade')
                
                # Se há cidade no POST, filtrar cartórios
                cidade_post = self.data.get('cidade')
                if cidade_post:
                    cartorios_cidade = Cartorios.objects.filter(
                        estado=estado_post,
                        cidade=cidade_post
                    ).order_by('nome')
                    self.fields['cartorio'].queryset = cartorios_cidade 