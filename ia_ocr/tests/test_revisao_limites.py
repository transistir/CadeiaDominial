"""Limites contextuais de campo (RG/CPF/cartório) — migração VERBATIM
de ``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do plano de
400 linhas). Corpos verbatim; só imports e a linha de classe mudam.
"""

from django.test import TestCase
from django.utils import timezone

from ia_ocr import valores
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import dados_revisados, desnormalizar, pendencias
from .factories import criar_documento_digital
from .payloads_extracao import SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro


class LimitesContextuaisTest(TestCase):
    """#296 item 1: o limite da identificação segue o tipo efetivo da parte.

    Sem o contexto, ``documento_identificacao/valor`` caía no limite genérico
    do ``SEM_DESTINO`` (10 000): um RG de 21 caracteres passava na revisão e
    só quebraria na importação (I-6). CPF conta apenas os dígitos — a máscara
    (``123.456.789-00``, 14 caracteres) não cabe no ``max_length=11``.
    """

    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(), status='revisado',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )

    @staticmethod
    def _campo(valor):
        return {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False, 'evidencia': None,
        }

    @classmethod
    def _identificacao(cls, tipo, valor):
        return {'tipo': cls._campo(tipo), 'valor': cls._campo(valor)}

    def _persistir(self, payload):
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        linhas = desnormalizar(self.extracao, payload, [self.pagina])
        for linha in linhas:
            if linha.tipo_valor in ('parte', 'cartorio'):
                linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return self.extracao

    def _payload_com_identificacao(self, tipo, valor):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][2]['documento_identificacao'] = (
            self._identificacao(tipo, valor)
        )
        return payload

    def _limites_da(self, chave):
        return [
            pendencia for pendencia in pendencias(self.extracao)
            if pendencia['chave'] == chave
            and pendencia['motivo'] == valores.MOTIVO_LIMITE
        ]

    CHAVE_VALOR = '/acts/0/partes/2/documento_identificacao/valor'

    def test_rg_acima_de_20_vira_pendencia(self):
        self._persistir(self._payload_com_identificacao('RG', 'x' * 21))

        self.assertEqual(self._limites_da(self.CHAVE_VALOR), [{
            'chave': self.CHAVE_VALOR,
            'motivo': valores.MOTIVO_LIMITE,
            'bloqueante': True,
        }])

    def test_rg_no_limite_de_20_passa_e_chega_a_dados_revisados(self):
        self._persistir(self._payload_com_identificacao('RG', 'x' * 20))
        self.extracao.finalizada_em = timezone.now()
        self.extracao.save()

        self.assertEqual(pendencias(self.extracao), [])
        dados = dados_revisados(self.extracao)
        parte = dados.atos[0].partes[2]
        self.assertEqual(parte.rg, 'x' * 20)
        self.assertIsNone(parte.cpf)

    def test_cpf_com_mascara_nao_bloqueia(self):
        self._persistir(
            self._payload_com_identificacao('CPF', '123.456.789-00')
        )

        self.assertEqual(pendencias(self.extracao), [])

    def test_trocar_o_tipo_para_rg_reavalia_o_valor(self):
        # 21 caracteres com 19 dígitos: CPF não casa por documento (≠ 11
        # dígitos) e fica em conferência; como RG, passa a caber em
        # Pessoas.rg (20) e o mesmo texto vira pendência.
        valor = 'AB' + '1' * 19
        self._persistir(self._payload_com_identificacao('CPF', valor))
        self.assertEqual(self._limites_da(self.CHAVE_VALOR), [])

        self.extracao.campos.filter(
            chave='/acts/0/partes/2/documento_identificacao/tipo',
        ).update(valor_final='RG')

        self.assertEqual(self._limites_da(self.CHAVE_VALOR), [{
            'chave': self.CHAVE_VALOR,
            'motivo': valores.MOTIVO_LIMITE,
            'bloqueante': True,
        }])

    def test_cartorio_acima_de_200_continua_bloqueado(self):
        # Regressão (#296 item 1): o limite do nome de cartório já era
        # contextual por chave e não pode regredir com a mudança.
        longo = self._campo('x' * 201)
        for nome_ponteiro, valor in (
            ('cartorio_transmissao', longo),
            ('origem/cartorio', longo),
        ):
            with self.subTest(ponteiro=nome_ponteiro):
                payload = payload_registro(self.job.job_id)
                if nome_ponteiro == 'origem/cartorio':
                    payload['acts'][0]['origem'] = {'cartorio': valor}
                else:
                    payload['acts'][0][nome_ponteiro] = valor
                self._persistir(payload)

                self.assertEqual(
                    self._limites_da(f'/acts/0/{nome_ponteiro}'),
                    [{
                        'chave': f'/acts/0/{nome_ponteiro}',
                        'motivo': valores.MOTIVO_LIMITE,
                        'bloqueante': True,
                    }],
                )
