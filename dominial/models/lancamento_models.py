from django.db import models
from django.core.exceptions import ValidationError


class LancamentoTipo(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('averbacao', 'Averbação'),
        ('registro', 'Registro'),
        ('inicio_matricula', 'Início de Matrícula')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    requer_transmissao = models.BooleanField(default=False)
    requer_detalhes = models.BooleanField(default=False)
    requer_titulo = models.BooleanField(default=False)
    requer_cartorio_origem = models.BooleanField(default=False)
    requer_livro_origem = models.BooleanField(default=False)
    requer_folha_origem = models.BooleanField(default=False)
    requer_data_origem = models.BooleanField(default=False)
    requer_forma = models.BooleanField(default=False)
    requer_descricao = models.BooleanField(default=False)
    requer_observacao = models.BooleanField(default=True)

    def __str__(self):
        return self.get_tipo_display()

    class Meta:
        verbose_name = "Tipo de Lançamento"
        verbose_name_plural = "Tipos de Lançamento"

    def clean(self):
        # Validações específicas por tipo
        if self.tipo == 'registro':
            if not self.requer_cartorio_origem:
                raise ValidationError("Registros devem requerer cartório de origem")
            if not self.requer_titulo:
                raise ValidationError("Registros devem requerer título")
        elif self.tipo == 'averbacao':
            if not self.requer_descricao:
                raise ValidationError("Averbações devem requerer descrição")


class Lancamento(models.Model):
    id = models.AutoField(primary_key=True)
    documento = models.ForeignKey('Documento', on_delete=models.CASCADE, related_name='lancamentos')
    tipo = models.ForeignKey(LancamentoTipo, on_delete=models.PROTECT)
    numero_lancamento = models.CharField(max_length=50, help_text="Número/código do lançamento gerado pelo cartório", null=True, blank=True)
    data = models.DateField()
    transmitente = models.ForeignKey('Pessoas', on_delete=models.PROTECT, related_name='transmitente_lancamento', null=True, blank=True)
    adquirente = models.ForeignKey('Pessoas', on_delete=models.PROTECT, related_name='adquirente_lancamento', null=True, blank=True)
    valor_transacao = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    origem = models.CharField(max_length=255, null=True, blank=True)
    detalhes = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    data_cadastro = models.DateField(auto_now_add=True)
    
    # Novos campos para tipos específicos
    forma = models.CharField(max_length=100, null=True, blank=True)
    descricao = models.TextField(null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    cartorio_origem = models.ForeignKey('Cartorios', on_delete=models.PROTECT, related_name='cartorio_origem_lancamento', null=True, blank=True)
    livro_origem = models.CharField(max_length=50, null=True, blank=True)
    folha_origem = models.CharField(max_length=50, null=True, blank=True)
    data_origem = models.DateField(null=True, blank=True)
    
    # Campo para indicar se é início de matrícula
    eh_inicio_matricula = models.BooleanField(default=False)
    
    # Campo para link com documento de origem (para cadeia dominial)
    documento_origem = models.ForeignKey('Documento', on_delete=models.PROTECT, related_name='lancamentos_origem', null=True, blank=True)

    class Meta:
        verbose_name = "Lançamento"
        verbose_name_plural = "Lançamentos"
        ordering = ['id']

    def __str__(self):
        return f"{self.tipo.get_tipo_display()} {self.numero_lancamento} - {self.documento.numero}"

    def clean(self):
        # Validar campos obrigatórios baseado no tipo de lançamento
        if self.tipo:
            if self.tipo.requer_cartorio_origem and not self.cartorio_origem:
                raise ValidationError("Cartório de origem é obrigatório para este tipo de lançamento")
            if self.tipo.requer_titulo and not self.titulo:
                raise ValidationError("Título é obrigatório para este tipo de lançamento")
            if self.tipo.requer_descricao and not self.descricao:
                raise ValidationError("Descrição é obrigatória para este tipo de lançamento")
            if self.tipo.requer_forma and not self.forma:
                raise ValidationError("Forma é obrigatória para este tipo de lançamento")


class LancamentoPessoa(models.Model):
    """Modelo para armazenar múltiplas pessoas com percentuais em um lançamento"""
    TIPO_CHOICES = [
        ('transmitente', 'Transmitente'),
        ('adquirente', 'Adquirente'),
    ]
    
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE, related_name='pessoas')
    pessoa = models.ForeignKey('Pessoas', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    percentual = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentual da participação (0-100)")
    nome_digitado = models.CharField(max_length=255, null=True, blank=True, help_text="Nome digitado caso pessoa não existisse")

    class Meta:
        verbose_name = "Pessoa do Lançamento"
        verbose_name_plural = "Pessoas do Lançamento"
        unique_together = ('lancamento', 'pessoa', 'tipo')

    def __str__(self):
        return f"{self.pessoa.nome} ({self.get_tipo_display()}) - {self.percentual}%"

    def clean(self):
        if self.percentual < 0 or self.percentual > 100:
            raise ValidationError("Percentual deve estar entre 0 e 100") 