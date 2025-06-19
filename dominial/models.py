from pyexpat import model
from django.db import models
from django.core.exceptions import ValidationError
#from django.contrib.gis.db import models


# Entidades do modelo de cadeia dominial (TIs, Imóveis, Pessoas, Cartórios)

class TIs(models.Model):
    id = models.AutoField(primary_key=True)
    terra_referencia = models.ForeignKey('TerraIndigenaReferencia', on_delete=models.PROTECT, null=True, blank=True)
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    etnia = models.CharField(max_length=50)
    data_cadastro = models.DateField(auto_now_add=True)
    #poligonos = models.PolygonField(null=True, blank=True)  # Opcional, para armazenar polígonos geográficos
    class Meta:
        verbose_name = "TI"
        verbose_name_plural = "TIs"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.terra_referencia:
            self.nome = self.terra_referencia.nome
            self.codigo = self.terra_referencia.codigo
            self.etnia = self.terra_referencia.etnia
        super().save(*args, **kwargs)

class Cartorios(models.Model):
    nome = models.CharField(max_length=200)
    cns = models.CharField(max_length=20, unique=True)
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.estado}" if self.cidade and self.estado else self.nome

    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['estado', 'cidade', 'nome']

class Pessoas(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=11, unique=True) # Verificar formato (Cadastro de Pessoa Física - CPF)
    rg = models.CharField(max_length=20, null=True, blank=True) # Opcional, Registro Geral
    data_nascimento = models.DateField(null=True, blank=True) # Opcional, para data de nascimento
    email = models.EmailField(null=True, blank=True) # Opcional, para email
    telefone = models.CharField(max_length=15, null=True, blank=True) # Opcional, para telefone

    class Meta:
        verbose_name = "Pessoa"
        verbose_name_plural = "Pessoas"
    
    def __str__(self):
        return self.nome
    
class Imovel(models.Model):
    id = models.AutoField(primary_key=True)
    terra_indigena_id = models.ForeignKey(TIs, on_delete=models.PROTECT) 
    nome = models.CharField(max_length=100) # Obrigatório?
    proprietario = models.ForeignKey(Pessoas, on_delete=models.PROTECT) # Verificar 'on_delete'
    matricula = models.CharField(max_length=50, unique=True) # Verificar formato (Código Nacional de Matrícula - CNM ?? )
    sncr = models.CharField(max_length=50, unique=True) # Obrigatório, Sistema Nacional de Cadastro Rural (SNCR)
    sigef = models.CharField(max_length=50, null=True, blank=True) # Opcional, para SIGEF (Sistema de Gestão Fundiária)
    descricao = models.TextField(null=True, blank=True) # Opcional, para descrição do imóvel
    observacoes = models.TextField(null=True, blank=True) # Opcional, para observações adicionais
    cartorio = models.ForeignKey(Cartorios, on_delete=models.PROTECT, null=True, blank=True) # Cartório onde o imóvel está registrado
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro do imóvel

    class Meta:
        verbose_name = "Imóvel"
        verbose_name_plural = "Imóveis"
    
    
    def __str__(self):
        return self.matricula


# Tabelas de relacionamento entre entidades

# TIs e Imóveis (associação entre TIs e Imóveis) deixar aberto a possibilidade de verigicar sobreposicao geografica

class TIs_Imovel(models.Model):
    tis_codigo = models.ForeignKey(TIs, on_delete=models.CASCADE, related_name='tis_codigo')
    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='imovel')
    def __str__(self):
        return self.tis_codigo.nome + " - " + self.imovel.nome

# Tipos de alterações no modelo de cadeia dominial (Registro, Averbação, etc.)
# Dependendo do tipo de alteração, pode ser necessário criar tabelas adicionais para registros e averbações específicas

class AlteracoesTipo(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('registro', 'Registro'),
        ('averbacao', 'Averbação'),
        ('nao_classificado', 'Não Classificado')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)

    def __str__(self):
        return self.tipo

class RegistroTipo(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo

class AverbacoesTipo(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo


# Registro de alterações no modelo de cadeia dominial (Registro, Averbação, etc.)


class Alteracoes(models.Model):
    id = models.AutoField(primary_key=True)
    imovel_id = models.ForeignKey(Imovel, on_delete=models.CASCADE) # Verificar qual atributo usar para o relacionamento com Imóvel
    tipo_alteracao_id = models.ForeignKey(AlteracoesTipo, on_delete=models.CASCADE) # Verificar 'on_delete'
    livro = models.CharField(max_length=50, null=True, blank=True)
    folha = models.CharField(max_length=50, null=True, blank=True)
    cartorio = models.ForeignKey(Cartorios, on_delete=models.CASCADE) # Verificar 'on_delete'
    data_alteracao = models.DateField(null=True, blank=True) # Opcional, para data da alteração a ser registrada
    registro_tipo = models.ForeignKey(RegistroTipo, on_delete=models.CASCADE, null=True, blank=True) # Opcional, para tipo de registro
    averbacao_tipo = models.ForeignKey(AverbacoesTipo, on_delete=models.CASCADE, null=True, blank=True) # Opcional, para tipo de averbação
    titulo = models.CharField(max_length=255, null=True, blank=True) # Opcional, para título do registro ou averbação
    cartorio_origem = models.ForeignKey(Cartorios, on_delete=models.CASCADE, related_name='cartorio_responsavel') # Cartório responsável pela alteração
    livro_origem = models.CharField(max_length=50, null=True, blank=True) # Opcional, para livro de alteração de registro original
    folha_origem = models.CharField(max_length=50, null=True, blank=True) # Opcional, para folha de alteração de registro original
    data_origem = models.DateField(null=True, blank=True) # Opcional, para data de registro original
    transmitente = models.ForeignKey(Pessoas, on_delete=models.CASCADE, related_name='transmitente', null=True, blank=True) # Opcional, para pessoa que transmite o imóvel
    adquirente = models.ForeignKey(Pessoas, on_delete=models.CASCADE, related_name='adquirente', null=True, blank=True) # Opcional, para pessoa que adquire o imóvel
    valor_transacao = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Opcional, para valor da transação
    area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Opcional, para área do imóvel
    observacoes = models.TextField(null=True, blank=True) # Opcional, para observações adicionais
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro da alteração

    class Meta:
        verbose_name = "Alteração"
        verbose_name_plural = "Alterações"

    
    def __str__(self):
        return f"{self.imovel_id} - {self.tipo_alteracao_id} - {self.data_alteracao}" if self.data_alteracao else f"{self.imovel_id} - {self.tipo_alteracao_id}"

class TerraIndigenaReferencia(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    etnia = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)
    municipio = models.CharField(max_length=255, blank=True, null=True)
    area_ha = models.FloatField(blank=True, null=True)
    fase = models.CharField(max_length=100, blank=True, null=True)
    modalidade = models.CharField(max_length=100, blank=True, null=True)
    coordenacao_regional = models.CharField(max_length=100, blank=True, null=True)
    data_regularizada = models.DateField(blank=True, null=True)
    data_homologada = models.DateField(blank=True, null=True)
    data_declarada = models.DateField(blank=True, null=True)
    data_delimitada = models.DateField(blank=True, null=True)
    data_em_estudo = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    class Meta:
        verbose_name = "Terra Indígena (Referência)"
        verbose_name_plural = "Terras Indígenas (Referência)"
        ordering = ['nome']

class ImportacaoCartorios(models.Model):
    estado = models.CharField(max_length=2)
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    total_cartorios = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pendente', 'Pendente'),
            ('em_andamento', 'Em Andamento'),
            ('concluido', 'Concluído'),
            ('erro', 'Erro'),
        ],
        default='pendente'
    )
    erro = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Importação de Cartórios'
        verbose_name_plural = 'Importações de Cartórios'
        ordering = ['-data_inicio']

    def __str__(self):
        return f'Importação {self.estado} - {self.get_status_display()}'

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
    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='documentos')
    tipo = models.ForeignKey(DocumentoTipo, on_delete=models.PROTECT)
    numero = models.CharField(max_length=50)
    data = models.DateField()
    cartorio = models.ForeignKey(Cartorios, on_delete=models.PROTECT)
    livro = models.CharField(max_length=50)
    folha = models.CharField(max_length=50)
    origem = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    data_cadastro = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        unique_together = ('numero', 'cartorio')
        ordering = ['-data']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.numero}"

    def clean(self):
        # Verificar se o imóvel está sobreposto a uma terra indígena
        if not self.imovel.terra_indigena_id:
            raise ValidationError('O imóvel deve estar sobreposto a uma terra indígena')

class LancamentoTipo(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('averbacao', 'Averbação'),
        ('registro', 'Registro'),
        ('encerrar_matricula', 'Encerrar Matrícula'),
        ('inicio_matricula', 'Início de Matrícula'),
        ('transcricao', 'Transcrição')
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
            self.requer_titulo = True
            self.requer_cartorio_origem = True
            self.requer_livro_origem = True
            self.requer_folha_origem = True
            self.requer_data_origem = True
        elif self.tipo == 'averbacao':
            self.requer_forma = True
            self.requer_descricao = True
        elif self.tipo == 'encerrar_matricula':
            self.requer_forma = True
            self.requer_descricao = True

class Lancamento(models.Model):
    id = models.AutoField(primary_key=True)
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='lancamentos')
    tipo = models.ForeignKey(LancamentoTipo, on_delete=models.PROTECT)
    numero_lancamento = models.CharField(max_length=50, help_text="Número/código do lançamento gerado pelo cartório")
    data = models.DateField()
    transmitente = models.ForeignKey(Pessoas, on_delete=models.PROTECT, related_name='transmitente_lancamento', null=True, blank=True)
    adquirente = models.ForeignKey(Pessoas, on_delete=models.PROTECT, related_name='adquirente_lancamento', null=True, blank=True)
    valor_transacao = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    origem = models.CharField(max_length=255, null=True, blank=True)
    detalhes = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    data_cadastro = models.DateField(auto_now_add=True)
    
    # Novos campos para tipos específicos
    forma = models.CharField(max_length=100, null=True, blank=True)
    descricao = models.TextField(null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    cartorio_origem = models.ForeignKey(Cartorios, on_delete=models.PROTECT, related_name='cartorio_origem_lancamento', null=True, blank=True)
    livro_origem = models.CharField(max_length=50, null=True, blank=True)
    folha_origem = models.CharField(max_length=50, null=True, blank=True)
    data_origem = models.DateField(null=True, blank=True)
    
    # Campo para indicar se é início de matrícula
    eh_inicio_matricula = models.BooleanField(default=False)
    
    # Campo para link com documento de origem (para cadeia dominial)
    documento_origem = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name='lancamentos_origem', null=True, blank=True)

    class Meta:
        verbose_name = "Lançamento"
        verbose_name_plural = "Lançamentos"
        ordering = ['-data']

    def __str__(self):
        numero_ref = f" #{self.numero_lancamento}" if self.numero_lancamento else ""
        return f"{self.tipo.get_tipo_display()}{numero_ref} - {self.data}"

    def clean(self):
        # Validar campos obrigatórios baseado no tipo de lançamento
        if self.tipo:
            if self.tipo.requer_titulo and not self.titulo:
                raise ValidationError('Título é obrigatório para este tipo de lançamento.')
            if self.tipo.requer_forma and not self.forma:
                raise ValidationError('Forma é obrigatória para este tipo de lançamento.')
            if self.tipo.requer_descricao and not self.descricao:
                raise ValidationError('Descrição é obrigatória para este tipo de lançamento.')
            if self.tipo.requer_cartorio_origem and not self.cartorio_origem:
                raise ValidationError('Cartório de origem é obrigatório para este tipo de lançamento.')
            if self.tipo.requer_livro_origem and not self.livro_origem:
                raise ValidationError('Livro de origem é obrigatório para este tipo de lançamento.')
            if self.tipo.requer_folha_origem and not self.folha_origem:
                raise ValidationError('Folha de origem é obrigatória para este tipo de lançamento.')
            if self.tipo.requer_data_origem and not self.data_origem:
                raise ValidationError('Data de origem é obrigatória para este tipo de lançamento.')