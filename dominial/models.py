from pyexpat import model
from django.db import models
#from django.contrib.gis.db import models


# Entidades do modelo de cadeia dominial (TIs, Imóveis, Pessoas, Cartórios)

class TIs(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    etnia = models.CharField(max_length=50)
    data_cadastro = models.DateField(auto_now_add=True)
    #poligonos = models.PolygonField(null=True, blank=True)  # Opcional, para armazenar polígonos geográficos
    
    def __str__(self):
        return self.nome

class Cartorios(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    cns = models.CharField(max_length=50, unique=True) # Formato de registro dos cartórios? Código do Cartório (CNS) ??
    endereco = models.CharField(max_length=255, null=True, blank=True) # Opcional
    telefone = models.CharField(max_length=15, null=True, blank=True) # Opcional
    email = models.EmailField(null=True, blank=True) # Opcional

    def __str__(self):
        return self.nome
    
class Pessoas(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=11, unique=True) # Verificar formato (Cadastro de Pessoa Física - CPF)
    rg = models.CharField(max_length=20, null=True, blank=True) # Opcional, Registro Geral
    data_nascimento = models.DateField(null=True, blank=True) # Opcional, para data de nascimento
    email = models.EmailField(null=True, blank=True) # Opcional, para email
    telefone = models.CharField(max_length=15, null=True, blank=True) # Opcional, para telefone
    
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
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro do imóvel
    
    
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
    
    def __str__(self):
        return f"{self.imovel_id} - {self.tipo_alteracao_id} - {self.data_alteracao}" if self.data_alteracao else f"{self.imovel_id} - {self.tipo_alteracao_id}"