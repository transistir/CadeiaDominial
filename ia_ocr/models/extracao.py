from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .job import OcrJob

STATUS_REVISAO_CHOICES = [
    ('sugerido', 'Sugerido'),
    ('aceito', 'Aceito'),
    ('editado', 'Editado'),
    ('descartado', 'Descartado'),
    ('importado', 'Importado'),
]

TIPO_VALOR_CHOICES = [
    ('texto', 'Texto'),
    ('data', 'Data'),
    ('decimal', 'Decimal'),
    ('area', 'Área'),
    ('booleano', 'Booleano'),
    ('enum', 'Enum'),
    ('cartorio', 'Cartório'),
    ('parte', 'Parte'),
    ('ato', 'Ato'),
]


class ExtracaoSugerida(models.Model):
    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.CASCADE, related_name='extracoes'
    )
    schema_version = models.CharField(max_length=50)
    payload = models.JSONField()
    provider = models.CharField(max_length=100)
    # Cópia do payload conforme devolvido pelo serviço de extração: o
    # desdobramento em CampoSugerido parte dela, não do payload bruto.
    payload_servico = models.JSONField()
    solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    finalizada_em = models.DateTimeField(null=True, blank=True)
    finalizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Extração sugerida'
        verbose_name_plural = 'Extrações sugeridas'
        constraints = [
            models.UniqueConstraint(
                fields=['ocr_job'],
                condition=Q(finalizada_em__isnull=False),
                name='uniq_extracao_finalizada_por_job',
            ),
        ]

    def __str__(self):
        return f'Extração {self.schema_version} do job {self.ocr_job_id}'


class CampoSugerido(models.Model):
    extracao = models.ForeignKey(
        ExtracaoSugerida, on_delete=models.CASCADE, related_name='campos'
    )
    chave = models.CharField(max_length=255)
    raw = models.TextField(null=True, blank=True)
    normalized = models.TextField(null=True, blank=True)
    tipo_valor = models.CharField(
        max_length=20, choices=TIPO_VALOR_CHOICES, default='texto'
    )
    confianca = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    requer_revisao = models.BooleanField(default=False)
    motivos_revisao = models.JSONField(default=list, blank=True)
    match_candidatos = models.JSONField(default=list, blank=True)
    pessoa_escolhida = models.ForeignKey(
        'dominial.Pessoas',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    cartorio_escolhido = models.ForeignKey(
        'dominial.Cartorios',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    criar_novo = models.BooleanField(default=False)
    area_convertida = models.BooleanField(default=False)
    evidencia_pagina = models.PositiveIntegerField(null=True, blank=True)
    evidencia_trecho = models.TextField(blank=True)
    # bbox do trecho na página, em pixels do OCR (decisão #290/17-10):
    # [x0, y0, x1, y1] quando o serviço fornece; NULL quando não fornece ou
    # o formato não é reconhecível. A conversão pixel→ponto de PDF é do
    # template (usa o dpi do job), não desta camada.
    evidencia_bbox = models.JSONField(null=True, blank=True)
    status_revisao = models.CharField(
        max_length=20, choices=STATUS_REVISAO_CHOICES, default='sugerido'
    )
    valor_final = models.TextField(null=True, blank=True)
    # Separa "qual é o valor" (``valor_final``) de "o revisor ESCOLHEU esse
    # valor": conferir/reenviar o mesmo valor do OCR limpa o ``valor_final``
    # (canonico == normalized) sem apagar a decisão — a precedência do tipo
    # (#322) precisa enxergar a escolha explícita mesmo com o valor nulo.
    escolha_explicita = models.BooleanField(default=False)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    revisado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Campo sugerido'
        verbose_name_plural = 'Campos sugeridos'
        constraints = [
            models.UniqueConstraint(
                fields=['extracao', 'chave'],
                name='uniq_campo_por_extracao_chave',
            ),
        ]

    def __str__(self):
        return f"{self.chave} ({self.get_status_revisao_display()})"
