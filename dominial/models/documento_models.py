from django.db import models
from django.core.exceptions import ValidationError


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
    data = models.DateField()
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT)
    livro = models.CharField(max_length=50)
    folha = models.CharField(max_length=50)
    origem = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    data_cadastro = models.DateField(auto_now_add=True)
    nivel_manual = models.IntegerField(null=True, blank=True, help_text="Nível manual na árvore da cadeia dominial (0-10)")
    
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
        unique_together = ('numero', 'cartorio')
        ordering = ['-data']

    def __str__(self):
        return f"{self.tipo.get_tipo_display()} {self.numero} - {self.cartorio.nome}"

    def clean(self):
        # Verificar se o imóvel está sobreposto a uma terra indígena
        pass 