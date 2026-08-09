from datetime import date

from django.db import models
from django.core.exceptions import ValidationError

from .identidade_expressions import numero_documento_normalizado_expression

# Data fictícia gravada por engano em documentos de matrícula criados
# automaticamente antes da correção da issue #120.
DATA_FICTICIA_LEGADO = date(2024, 1, 1)


class DocumentoTipo(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('transcricao', 'Transcrição'),
        ('matricula', 'Matrícula')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)

    def __str__(self):
        return self.get_tipo_display()

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"


class Documento(models.Model):
    id = models.AutoField(primary_key=True)
    imovel = models.ForeignKey('Imovel', on_delete=models.CASCADE, related_name='documentos')
    tipo = models.ForeignKey(DocumentoTipo, on_delete=models.PROTECT)
    numero = models.CharField(max_length=50)
    numero_normalizado = models.GeneratedField(
        expression=numero_documento_normalizado_expression('numero'),
        output_field=models.CharField(max_length=50),
        db_persist=True,
        editable=False,
    )
    data = models.DateField()
    data_presumida = models.BooleanField(
        default=False,
        help_text='True quando a data não é um dado jurídico real, mas a data de cadastro no sistema.',
    )
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT)
    livro = models.CharField(max_length=50)
    folha = models.CharField(max_length=50)
    origem = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    data_cadastro = models.DateField(auto_now_add=True)
    nivel_manual = models.IntegerField(null=True, blank=True, help_text="Nível manual na árvore da cadeia dominial (0-10)")
    
    # Campo para classificação de fim de cadeia
    classificacao_fim_cadeia = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('origem_lidima', 'Imóvel com Origem Lídima'),
            ('sem_origem', 'Imóvel sem Origem'),
            ('inconclusa', 'Situação Inconclusa'),
        ],
        verbose_name='Classificação do Fim de Cadeia',
        help_text='Classificação específica para documentos de fim de cadeia'
    )
    
    # Campo para sigla do patrimônio público
    sigla_patrimonio_publico = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Sigla do Patrimônio Público',
        help_text='Sigla específica do patrimônio público (ex: INCRA, Estado, etc.)'
    )
    
    # NOVOS CAMPOS PARA CRI
    cri_atual = models.ForeignKey(
        'Cartorios', 
        on_delete=models.PROTECT, 
        related_name='documentos_cri_atual',
        null=True, 
        blank=True,
        verbose_name='CRI Atual',
        help_text='Cartório de Registro de Imóveis atual do documento'
    )
    cri_origem = models.ForeignKey(
        'Cartorios', 
        on_delete=models.PROTECT, 
        related_name='documentos_cri_origem',
        null=True, 
        blank=True,
        verbose_name='CRI da Origem',
        help_text='Cartório de Registro de Imóveis da origem (quando criado automaticamente)'
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'numero_normalizado', 'cartorio'],
                name='unique_documento_identidade_canonica',
            ),
        ]
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.tipo.get_tipo_display()} {self.numero} - {self.cartorio.nome}"

    @property
    def label_data(self):
        """Label contextual para exibição da data."""
        return 'Análise iniciada em' if self.data_presumida else 'Data'

    @property
    def data_exibicao(self):
        """Data apropriada para exibição.

        Documentos com data presumida ou com a data fictícia de legado
        (2024-01-01) exibem `data_cadastro` — a data real em que o documento
        foi criado no sistema — em vez da data sem valor jurídico.
        """
        if self.data_presumida or self.data == DATA_FICTICIA_LEGADO:
            return self.data_cadastro
        return self.data

    @staticmethod
    def data_exibicao_expression():
        """Expressão SQL equivalente a ``data_exibicao`` para ordenação."""
        return models.Case(
            models.When(
                models.Q(data_presumida=True) | models.Q(data=DATA_FICTICIA_LEGADO),
                then=models.F('data_cadastro'),
            ),
            default=models.F('data'),
            output_field=models.DateField(),
        )

    def clean(self):
        # Verificar se o imóvel está sobreposto a uma terra indígena
        pass
