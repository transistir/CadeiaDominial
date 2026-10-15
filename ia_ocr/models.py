import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import transaction
from django.db import models
from django.utils import timezone

from .estados import (
    CONCLUIDO, FALHOU, PENDENTE, STATUS_CHOICES, TEXTO_CONFIRMADO,
    TRANSICOES_VALIDAS, TransicaoConcorrente, TransicaoInvalida,
)

ORIGEM_CHOICES = [
    ('ocr', 'OCR'),
    ('texto_embutido', 'Texto embutido'),
]

STATUS_REVISAO_CHOICES = [
    ('sugerido', 'Sugerido'),
    ('aceito', 'Aceito'),
    ('editado', 'Editado'),
    ('descartado', 'Descartado'),
    ('importado', 'Importado'),
]


class OcrJob(models.Model):
    documento_digital = models.ForeignKey(
        'dominial.DocumentoDigital',
        on_delete=models.PROTECT,
        related_name='ocr_jobs',
    )
    job_id = models.UUIDField(unique=True, default=uuid.uuid4)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=PENDENTE
    )
    tentativa = models.PositiveIntegerField(default=1)
    erro_codigo = models.CharField(max_length=100, blank=True)
    erro_mensagem = models.TextField(blank=True)
    sha256_pdf = models.CharField(max_length=64, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    timings_ms = models.JSONField(null=True, blank=True)
    origem = models.CharField(
        max_length=20, choices=ORIGEM_CHOICES, default='ocr'
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ocr_jobs_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Job de OCR'
        verbose_name_plural = 'Jobs de OCR'
        ordering = ['-criado_em']

    def __str__(self):
        # Nunca o documento/nome do arquivo: __str__ entra em tracebacks
        # (ProtectedError carrega os objetos) e nome de PDF é PII.
        return f'Job de OCR {self.job_id} ({self.status})'

    def transicionar(self, para, de_status=None, usuario=None, motivo='',
                     tentativa=None, erro_codigo=None, erro_mensagem=None):
        """Transiciona o job com compare-and-swap no estado persistido.

        O UPDATE é condicionado a (pk, status esperado, tentativa) — a
        tentativa (token do lease) SEMPRE faz parte do CAS, mesmo quando o
        argumento é omitido (usa self.tentativa): sem isso, um objeto velho
        da tentativa N encerraria a tentativa N+1 de outro worker. Se outra
        transação ganhou antes (rowcount 0), nada é gravado — nem status,
        nem auditoria — e `TransicaoConcorrente` é levantada.
        """
        de = de_status if de_status is not None else self.status
        if para not in TRANSICOES_VALIDAS.get(de, set()):
            raise TransicaoInvalida(
                f'Transição inválida: {de} → {para}.',
                code='transicao_invalida',
            )
        if de == FALHOU and para == PENDENTE:
            raise TransicaoInvalida(
                'falhou → pendente só é permitida via retry().',
                code='transicao_invalida',
            )

        filtros = {
            'pk': self.pk,
            'status': de,
            'tentativa': tentativa if tentativa is not None else self.tentativa,
        }
        campos = {'status': para, 'atualizado_em': timezone.now()}
        if para == FALHOU:
            campos['erro_codigo'] = erro_codigo or ''
            campos['erro_mensagem'] = erro_mensagem or ''

        with transaction.atomic():
            rowcount = type(self).objects.filter(**filtros).update(**campos)
            if rowcount == 0:
                raise TransicaoConcorrente(
                    f'CAS perdido: job {self.job_id} não está mais em {de} '
                    f'(tentativa {filtros["tentativa"]}).'
                )
            if de == CONCLUIDO and para == TEXTO_CONFIRMADO:
                # Pré-condição validada DEPOIS do CAS vencedor, dentro do
                # atomic (sem TOCTOU): falha aqui → rollback do UPDATE.
                self._validar_confirmacao_de_texto()
            OcrJobTransicao.objects.create(
                ocr_job_id=self.pk,
                de_status=de,
                para_status=para,
                usuario=usuario,
                motivo=motivo,
            )

        # Espelha em memória o que foi persistido.
        self.status = para
        self.atualizado_em = campos['atualizado_em']
        if para == FALHOU:
            self.erro_codigo = campos['erro_codigo']
            self.erro_mensagem = campos['erro_mensagem']
        return True

    def retry(self, usuario=None, motivo=''):
        """Reenfileira um job `falhou`: volta a `pendente` e incrementa a tentativa.

        A tentativa é o token do lease do worker: incrementá-la invalida
        finalizações tardias de workers antigos. Páginas existentes são
        preservadas (a política de sobrescrita é da issue I-2).
        """
        if self.status != FALHOU:
            raise TransicaoInvalida(
                f'retry só é permitido a partir de {FALHOU} (status atual: {self.status}).',
                code='transicao_invalida',
            )
        agora = timezone.now()
        with transaction.atomic():
            rowcount = type(self).objects.filter(
                pk=self.pk, status=FALHOU, tentativa=self.tentativa,
            ).update(
                status=PENDENTE,
                tentativa=self.tentativa + 1,
                erro_codigo='',
                erro_mensagem='',
                atualizado_em=agora,
            )
            if rowcount == 0:
                raise TransicaoConcorrente(
                    f'CAS perdido: job {self.job_id} não está mais em {FALHOU}.'
                )
            OcrJobTransicao.objects.create(
                ocr_job_id=self.pk,
                de_status=FALHOU,
                para_status=PENDENTE,
                usuario=usuario,
                motivo=motivo,
            )
        self.status = PENDENTE
        self.tentativa += 1
        self.erro_codigo = ''
        self.erro_mensagem = ''
        self.atualizado_em = agora

    def _validar_confirmacao_de_texto(self):
        """concluido → texto_confirmado exige todas as páginas confirmadas.

        O critério é `confirmado_em` preenchido — página em branco/verso também
        é confirmável; job sem páginas não confirma.
        """
        paginas = self.paginas.all()
        if not paginas.exists():
            raise TransicaoInvalida(
                'Job sem páginas OCR: não há texto a confirmar.',
                code='sem_paginas',
            )
        if paginas.filter(confirmado_em__isnull=True).exists():
            raise TransicaoInvalida(
                'Existem páginas sem confirmado_em preenchido.',
                code='paginas_nao_confirmadas',
            )


class PaginaOcr(models.Model):
    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.CASCADE, related_name='paginas'
    )
    numero_pagina = models.PositiveIntegerField()
    texto_ocr = models.TextField()
    texto_confirmado = models.TextField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    confirmado_em = models.DateTimeField(null=True, blank=True)
    blocos = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'Página OCR'
        verbose_name_plural = 'Páginas OCR'
        unique_together = ('ocr_job', 'numero_pagina')
        ordering = ['numero_pagina']

    def __str__(self):
        # ocr_job_id (número da página + id): nunca o documento (PII).
        return f'Página {self.numero_pagina} do job {self.ocr_job_id}'


class ExtracaoSugerida(models.Model):
    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.CASCADE, related_name='extracoes'
    )
    schema_version = models.CharField(max_length=50)
    payload = models.JSONField()
    provider = models.CharField(max_length=100)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Extração sugerida'
        verbose_name_plural = 'Extrações sugeridas'

    def __str__(self):
        return f'Extração {self.schema_version} do job {self.ocr_job_id}'


class CampoSugerido(models.Model):
    extracao = models.ForeignKey(
        ExtracaoSugerida, on_delete=models.CASCADE, related_name='campos'
    )
    chave = models.CharField(max_length=255)
    raw = models.TextField()
    normalized = models.TextField()
    confianca = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    requer_revisao = models.BooleanField(default=False)
    evidencia_pagina = models.PositiveIntegerField(null=True, blank=True)
    evidencia_trecho = models.TextField(blank=True)
    status_revisao = models.CharField(
        max_length=20, choices=STATUS_REVISAO_CHOICES, default='sugerido'
    )
    valor_final = models.TextField(null=True, blank=True)
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

    def __str__(self):
        return f"{self.chave} ({self.get_status_revisao_display()})"


class OcrJobTransicao(models.Model):
    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.CASCADE, related_name='transicoes'
    )
    de_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    para_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    motivo = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transição de job de OCR'
        verbose_name_plural = 'Transições de jobs de OCR'
        ordering = ['criado_em']

    def __str__(self):
        return f'{self.de_status} → {self.para_status} (job {self.ocr_job_id})'
