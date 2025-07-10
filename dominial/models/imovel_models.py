from django.db import models


class Imovel(models.Model):
    id = models.AutoField(primary_key=True)
    terra_indigena_id = models.ForeignKey('TIs', on_delete=models.PROTECT) 
    nome = models.CharField(max_length=100) # Obrigatório?
    proprietario = models.ForeignKey('Pessoas', on_delete=models.PROTECT) # Verificar 'on_delete'
    matricula = models.CharField(max_length=50, unique=True) # Verificar formato (Código Nacional de Matrícula - CNM ?? )
    observacoes = models.TextField(null=True, blank=True) # Opcional, para observações adicionais
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT, null=True, blank=True) # Cartório onde o imóvel está registrado
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro do imóvel

    class Meta:
        verbose_name = "Imóvel"
        verbose_name_plural = "Imóveis"
    
    def __str__(self):
        return self.matricula


class Cartorios(models.Model):
    TIPO_CHOICES = [
        ('CRI', 'Cartório de Registro de Imóveis'),
        ('OUTRO', 'Outro'),
    ]
    
    nome = models.CharField(max_length=200)
    cns = models.CharField(max_length=20, unique=True)
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    tipo = models.CharField(
        max_length=10, 
        choices=TIPO_CHOICES, 
        default='CRI',
        verbose_name='Tipo de Cartório'
    )

    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.estado}" if self.cidade and self.estado else self.nome

    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['tipo', 'estado', 'cidade', 'nome']


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
        return f"Importação {self.estado} - {self.status}" 