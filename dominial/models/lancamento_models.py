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
    
    # Campos de cartório separados por contexto
    cartorio_origem = models.ForeignKey('Cartorios', on_delete=models.PROTECT, related_name='cartorio_origem_lancamento', null=True, blank=True, help_text="Cartório de origem (início de matrícula)")
    cartorio_transacao = models.ForeignKey('Cartorios', on_delete=models.PROTECT, related_name='cartorio_transacao_lancamento', null=True, blank=True, help_text="Cartório onde foi registrada a transmissão (legado)")
    cartorio_transmissao = models.ForeignKey('Cartorios', on_delete=models.PROTECT, related_name='cartorio_transmissao_lancamento', null=True, blank=True, help_text="Cartório onde foi registrada a transmissão (novo padrão)")
    
    # Campos de transação (separados dos campos de origem)
    livro_transacao = models.CharField(max_length=50, null=True, blank=True, help_text="Livro da transação")
    folha_transacao = models.CharField(max_length=50, null=True, blank=True, help_text="Folha da transação")
    data_transacao = models.DateField(null=True, blank=True, help_text="Data da transação")
    
    # Campos de origem (apenas para início de matrícula)
    livro_origem = models.CharField(max_length=50, null=True, blank=True, help_text="Livro da origem")
    folha_origem = models.CharField(max_length=50, null=True, blank=True, help_text="Folha da origem")
    data_origem = models.DateField(null=True, blank=True, help_text="Data da origem")
    
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
        
        # Validações para início de matrícula
        if self.tipo and self.tipo.tipo == 'inicio_matricula':
            # Para início de matrícula, cartório de origem é obrigatório
            if not self.cartorio_origem:
                raise ValidationError("Cartório de origem é obrigatório para início de matrícula")
    


    @property
    def transmitentes(self):
        return self.pessoas.filter(tipo='transmitente')

    @property
    def adquirentes(self):
        return self.pessoas.filter(tipo='adquirente')
    
    @property
    def cartorio_transmissao_compat(self):
        """
        Property para compatibilidade: retorna cartorio_transmissao se disponível,
        senão retorna cartorio_transacao (legado)
        """
        return self.cartorio_transmissao or self.cartorio_transacao


class LancamentoPessoa(models.Model):
    """Modelo para armazenar múltiplas pessoas com percentuais em um lançamento"""
    TIPO_CHOICES = [
        ('transmitente', 'Transmitente'),
        ('adquirente', 'Adquirente'),
    ]
    
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE, related_name='pessoas')
    pessoa = models.ForeignKey('Pessoas', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nome_digitado = models.CharField(max_length=255, null=True, blank=True, help_text="Nome digitado caso pessoa não existisse")

    class Meta:
        verbose_name = "Pessoa do Lançamento"
        verbose_name_plural = "Pessoas do Lançamento"
        unique_together = ('lancamento', 'pessoa', 'tipo')

    def __str__(self):
        return f"{self.pessoa.nome} ({self.get_tipo_display()})" 


class OrigemFimCadeia(models.Model):
    """
    Modelo para armazenar informações de fim de cadeia por origem individual
    """
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE, related_name='origens_fim_cadeia')
    indice_origem = models.IntegerField(help_text="Índice da origem no array de origens (0, 1, 2, ...)")
    fim_cadeia = models.BooleanField(default=False, help_text="Indica se esta origem marca o fim da cadeia")
    tipo_fim_cadeia = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        choices=[
            ('destacamento_publico', 'Destacamento do Patrimônio Público'),
            ('outra', 'Outra'),
            ('sem_origem', 'Sem Origem'),
        ],
        help_text="Tipo do fim de cadeia para esta origem"
    )
    especificacao_fim_cadeia = models.TextField(
        null=True, 
        blank=True,
        help_text="Especificação quando o tipo é 'Outra' para esta origem"
    )
    classificacao_fim_cadeia = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('origem_lidima', 'Imóvel com Origem Lídima'),
            ('sem_origem', 'Imóvel sem Origem'),
            ('inconclusa', 'Situação Inconclusa'),
        ],
        help_text="Classificação do imóvel quando a cadeia termina nesta origem"
    )

    class Meta:
        unique_together = ['lancamento', 'indice_origem']
        verbose_name = "Origem Fim de Cadeia"
        verbose_name_plural = "Origens Fim de Cadeia"

    def __str__(self):
        return f"Origem {self.indice_origem} - Fim Cadeia: {self.fim_cadeia}"

    def clean(self):
        if self.fim_cadeia:
            if not self.tipo_fim_cadeia:
                raise ValidationError("Tipo do fim de cadeia é obrigatório quando 'Fim de Cadeia' está ativo")
            if not self.classificacao_fim_cadeia:
                raise ValidationError("Classificação do fim de cadeia é obrigatória quando 'Fim de Cadeia' está ativo")
            if self.tipo_fim_cadeia == 'outra' and not self.especificacao_fim_cadeia:
                raise ValidationError("Especificação é obrigatória quando o tipo é 'Outra'") 