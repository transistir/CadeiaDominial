import uuid

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone

from ..estados import (
    CONCLUIDO, EM_EXECUCAO, EXTRAIDO, FALHOU, PENDENTE, STATUS_CHOICES,
    TEXTO_CONFIRMADO, TRANSICOES_VALIDAS, TransicaoConcorrente,
    TransicaoInvalida,
)

ORIGEM_CHOICES = [
    ('ocr', 'OCR'),
    ('texto_embutido', 'Texto embutido'),
]

# Estados de revisão do texto de uma página (I-4 / #261). Não são coluna:
# derivam de confirmado_em / texto_confirmado, que existem desde a I-1.
ESTADO_NAO_CONFIRMADA = 'nao_confirmada'
ESTADO_CONFIRMADA = 'confirmada'
ESTADO_EDITADA = 'editada'

ESTADO_PAGINA_ROTULOS = {
    ESTADO_NAO_CONFIRMADA: 'Não confirmada',
    ESTADO_CONFIRMADA: 'Confirmada',
    ESTADO_EDITADA: 'Editada — reconfirmar',
}


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
    forcar_ocr = models.BooleanField(default=False)
    lease_expira_em = models.DateTimeField(null=True, blank=True, db_index=True)
    # Reserva da fase de extração (I-5): o serviço de extração segura o job
    # por um intervalo curto sem correr risco de dois extratores simultâneos.
    extracao_reserva = models.UUIDField(null=True, blank=True)
    extracao_reservada_ate = models.DateTimeField(null=True, blank=True)
    erro_codigo = models.CharField(max_length=100, blank=True)
    erro_mensagem = models.TextField(blank=True)
    sha256_pdf = models.CharField(max_length=64, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    # dpi efetivo usado no OCR do job: o cliente manda `dpi` (default 200)
    # sem que o serviço o persista (ocr_client.py ao montar os campos).
    # Guardar aqui permite converter bbox em coordenada de PDF depois.
    dpi = models.PositiveIntegerField(null=True, blank=True)
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
        indexes = [
            models.Index(
                fields=['status', 'criado_em', 'id'],
                name='iaocr_job_claim_idx',
            ),
            models.Index(
                fields=['status', 'atualizado_em'],
                name='iaocr_job_reap_idx',
            ),
        ]

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
            if de in {CONCLUIDO, TEXTO_CONFIRMADO} and para == EXTRAIDO:
                self._validar_extracao()
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

        Recusa com `TransicaoInvalida` apenas quando existe OUTRO job do
        mesmo documento em em_execucao (o próprio job não conta): retry é
        o caminho de RECUPERAÇÃO (reap/suporte) e bloquear por um vizinho
        apenas pendente deixaria o job preso em falhou para sempre — a
        guarda completa (pendente OU em_execucao) é do caminho de usuário,
        `services.reprocessar`. Mesma trava deste (transação +
        `select_for_update` no DocumentoDigital): dois retries concorrentes
        do mesmo documento não executam em duplicata.
        """
        if self.status != FALHOU:
            raise TransicaoInvalida(
                f'retry só é permitido a partir de {FALHOU} (status atual: {self.status}).',
                code='transicao_invalida',
            )
        # Import local: models.py carrega durante o setup dos apps e não pode
        # importar dominial.models no topo (ordem de INSTALLED_APPS).
        from dominial.models import DocumentoDigital

        agora = timezone.now()
        with transaction.atomic():
            DocumentoDigital.objects.select_for_update().get(
                pk=self.documento_digital_id
            )
            em_execucao = (
                type(self).objects
                .filter(
                    documento_digital_id=self.documento_digital_id,
                    status=EM_EXECUCAO,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if em_execucao:
                raise TransicaoInvalida(
                    'Existe outro job em_execucao para o documento: '
                    'execução concorrente duplicada.',
                    code='job_vigente_existente',
                )
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


    def _validar_extracao(self):
        """Ambos os caminhos para extraido exigem extração sugerida no job."""
        if not self.extracoes.exists():
            raise TransicaoInvalida(
                'Job sem extração sugerida: não há nada a revisar.',
                code='sem_extracao',
            )

    def extracao_vigente(self):
        """A extração mais recente do job (nenhuma: None)."""
        return self.extracoes.order_by('-id').first()


class PaginaOcr(models.Model):
    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.CASCADE, related_name='paginas'
    )
    numero_pagina = models.PositiveIntegerField()
    texto_ocr = models.TextField()
    # Texto devolvido pelo serviço de extração com as correções aplicadas
    # (decisão #290/16-10: o usuário NÃO confirma mais o texto do OCR — o
    # serviço devolve texto corrigido). Separado de texto_ocr para
    # preservar o original; `corrigido_em` marca quando a correção chegou.
    texto_corrigido = models.TextField(null=True, blank=True)
    corrigido_em = models.DateTimeField(null=True, blank=True)
    texto_confirmado = models.TextField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    confirmado_em = models.DateTimeField(null=True, blank=True)
    # Concorrência otimista: toda mutação do texto incrementa. O formulário da
    # tela devolve a versão que exibiu e o serviço recusa a obsoleta.
    versao = models.PositiveIntegerField(default=0)
    blocos = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'Página OCR'
        verbose_name_plural = 'Páginas OCR'
        unique_together = ('ocr_job', 'numero_pagina')
        ordering = ['numero_pagina']

    def __str__(self):
        # ocr_job_id (número da página + id): nunca o documento (PII).
        return f'Página {self.numero_pagina} do job {self.ocr_job_id}'

    @property
    def estado(self):
        """Estado de revisão do texto, derivado das colunas existentes.

        confirmada      — confirmado_em preenchido (critério de
                          OcrJob._validar_confirmacao_de_texto);
        editada         — há texto_confirmado salvo, mas sem confirmação:
                          edição que aguarda (re)confirmação;
        nao_confirmada  — nenhuma das duas.
        """
        if self.confirmado_em is not None:
            return ESTADO_CONFIRMADA
        if self.texto_confirmado is not None:
            return ESTADO_EDITADA
        return ESTADO_NAO_CONFIRMADA

    @property
    def estado_rotulo(self):
        return ESTADO_PAGINA_ROTULOS[self.estado]

    @property
    def texto_exibido(self):
        """Texto vigente da página: o confirmado/editado, ou o do OCR."""
        if self.texto_confirmado is not None:
            return self.texto_confirmado
        return self.texto_ocr

    @property
    def tem_edicao(self):
        """O texto vigente diverge do OCR original (há diff a mostrar)."""
        return (
            self.texto_confirmado is not None
            and self.texto_confirmado != self.texto_ocr
        )


class OcrJobTransicao(models.Model):
    # No monólito este modelo vinha depois de OcrJob no MESMO módulo:
    # `OcrJob.transicionar()/retry()` criam transições pelo nome global, então
    # ele precisa continuar visível no namespace deste módulo (registro.py
    # importaria de volta, o que é ciclo).
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
