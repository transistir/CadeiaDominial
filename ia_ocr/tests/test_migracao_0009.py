"""Migração 0009: backfill de ``escolha_explicita`` (P1, #322/PR #327).

A coluna nasce com ``default=False``; sem o ``RunPython`` da própria 0009,
linhas ``/acts/N/tipo_sugerido`` já confirmadas (``status_revisao``
'aceito'/'importado' com ``valor_final`` nulo) deixavam de contar como
decisão do revisor em ``revisao._valor_explicito`` — e o rótulo do OCR
('Av-5') vencia a sugestão confirmada ('registro') na importação.

P1 estendido (rodada 10): revisões já FINALIZADAS cujo card de tipo nunca
foi conferido (``status_revisao='sugerido'``) também são marcadas — em
revisão finalizada o ``normalized`` é o que o revisor viu e aprovou antes
do deploy; linha descartada e extração não finalizada continuam de fora.

A função do ``RunPython`` é chamada como o migrator chamaria: registry
real (``django.apps.apps``) e ``schema_editor=None``.
"""

import importlib

from django.apps import apps as apps_reais
from django.db import migrations
from django.test import TestCase
from django.utils import timezone

from dominial.models import LancamentoTipo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    dados_revisados, desnormalizar, pendencias, tipos_efetivos,
)
from ia_ocr.tests.factories import criar_documento_digital

from .payloads_extracao import SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro

MODULO_0009 = 'ia_ocr.migrations.0009_camposugerido_escolha_explicita'


def _runpython_da_0009():
    """A única operação ``RunPython`` da 0009, lida do módulo pelo caminho."""
    modulo = importlib.import_module(MODULO_0009)
    operacoes = [
        operacao for operacao in modulo.Migration.operations
        if isinstance(operacao, migrations.RunPython)
    ]
    assert len(operacoes) == 1, operacoes
    return operacoes[0]


class MontagemDa0009Test(TestCase):
    def test_runpython_unico_com_reverse_noop(self):
        runpython = _runpython_da_0009()
        self.assertIs(runpython.reverse_code, migrations.RunPython.noop)


class Backfill0009Test(TestCase):
    """``marcar_escolha_confirmada`` sobre o registry real da suíte."""

    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(),
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=True, requer_observacao=False,
        )
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )

    def _rodar_backfill(self):
        _runpython_da_0009().code(apps_reais, None)

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
        return {linha.chave: linha for linha in linhas}

    def _confirmacao_legada(self):
        """Revisão pré-0009: tipo 'aceito' com ``valor_final`` nulo.

        O rótulo 'Av-5' diverge da sugestão 'registro' de propósito: sem
        o backfill é ele que vence (o bug do P1). O resto do ato está
        completo para o tipo confirmado ('registro').
        """
        payload = payload_registro(self.job.job_id)
        titulo = 'Escritura Pública de Compra e Venda'
        payload['acts'][0]['titulo'] = {
            'raw': titulo, 'normalized': titulo, 'confianca': 0.95,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': titulo},
        }
        payload['acts'][0]['origem'] = {
            'cartorio': payload['document']['cartorio'].copy(),
        }
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        self._persistir(payload)
        # Estado legado: o card foi CONFERIDO ('aceito', valor_final nulo),
        # mas a flag ainda não existia.
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='aceito', valor_final=None, escolha_explicita=False,
        )

    def _campo(self, chave):
        return CampoSugerido.objects.get(chave=chave)

    def test_confirmacao_antiga_volta_a_vencer_o_rotulo_na_importacao(self):
        # (a) P1: 'aceito' + valor_final nulo + rótulo 'Av-5' → depois do
        # backfill a importação usa o tipo CONFIRMADO ('registro').
        self._confirmacao_legada()

        # Sem a flag, o rótulo 'Av-5' resolve 'averbacao' — o bug do P1.
        self.assertEqual(tipos_efetivos(self.extracao)['/acts/0'], 'averbacao')

        self._rodar_backfill()

        self.assertTrue(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )
        self.assertEqual(tipos_efetivos(self.extracao)['/acts/0'], 'registro')
        # Caminho real: a revisão finalizada devolve o tipo confirmado —
        # sem pendências e sem RevisaoInvalidada.
        self.assertEqual(pendencias(self.extracao), [])
        self.job.status = 'revisado'
        self.job.save()
        self.extracao.finalizada_em = timezone.now()
        self.extracao.save()
        dados = dados_revisados(self.extracao)
        self.assertEqual(len(dados.atos), 1)
        # NOTA (rodada 10): a asserção ``dados.atos[0].tipo == 'registro'``
        # passaria mesmo SEM o backfill — ``AtoRevisado.tipo`` lê
        # ``valor_final``/``normalized`` da linha antes de recorrer ao
        # resolvido. A prova do backfill é o PAR ``tipo_explicito`` +
        # ``tipos_efetivos`` (o que a importação ``_resolver_tipo_e_numero``
        # consome): sem a flag, ``tipo_explicito`` vinha None e o rótulo
        # decidia.
        self.assertEqual(dados.atos[0].tipo, 'registro')
        self.assertEqual(dados.atos[0].tipo_explicito, 'registro')

    def test_extracao_finalizada_marca_linha_sugerida(self):
        # (a) P1 estendido: revisão FINALIZADA cujo card de tipo nunca foi
        # conferido ('sugerido', valor_final nulo) — requer_revisao falso
        # não virou pendência e a finalização só gravou finalizada_em. O
        # revisor fechou vendo a sugestão 'registro' contra o rótulo 'Av-5'
        # (no develop o tipo vinha do normalized); sem a flag, o rótulo
        # passaria a vencer depois do deploy.
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='sugerido', valor_final=None,
        )
        self.extracao.finalizada_em = timezone.now()
        self.extracao.save()

        # Antes do backfill o rótulo 'Av-5' resolve 'averbacao'.
        self.assertEqual(tipos_efetivos(self.extracao)['/acts/0'], 'averbacao')

        self._rodar_backfill()

        self.assertTrue(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )
        self.assertEqual(tipos_efetivos(self.extracao)['/acts/0'], 'registro')
        # Caminho real: o que a importação (_resolver_tipo_e_numero)
        # consome é o tipo_explicito — a prova é ele, não o ``tipo``
        # (que lê valor_final/normalized antes).
        self.assertEqual(pendencias(self.extracao), [])
        self.job.status = 'revisado'
        self.job.save()
        dados = dados_revisados(self.extracao)
        self.assertEqual(dados.atos[0].tipo_explicito, 'registro')

    def test_extracao_finalizada_com_linha_descartada_nao_e_marcada(self):
        # (b) linha descartada não decide NEM em revisão finalizada: a
        # exclusão é decisão contrária, não aprovação do normalized.
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado', valor_final=None,
        )
        self.extracao.finalizada_em = timezone.now()
        self.extracao.save()

        self._rodar_backfill()

        self.assertFalse(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )

    def test_linha_sugerida_nao_e_marcada(self):
        # (c) extração NÃO finalizada com 'sugerido' → não marcada
        # (comportamento atual preservado: sem decisão gravada E sem
        # revisão fechada, a linha não é decisão do revisor).
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='sugerido',
        )
        self.assertIsNone(self.extracao.finalizada_em)

        self._rodar_backfill()

        self.assertFalse(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )

    def test_linha_descartada_nao_e_marcada(self):
        # (c) linha descartada não decide — não é marcada.
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado',
        )

        self._rodar_backfill()

        self.assertFalse(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )

    def test_linha_fora_de_tipo_sugerido_nao_e_marcada(self):
        # (d) o backfill é só da linha de tipo: 'aceito' em outra chave
        # não ganha a flag.
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='sugerido',
        )
        CampoSugerido.objects.filter(chave='/document/numero').update(
            status_revisao='aceito',
        )

        self._rodar_backfill()

        self.assertFalse(self._campo('/document/numero').escolha_explicita)
        self.assertFalse(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )

    def test_linha_importada_tambem_e_marcada(self):
        # 'importado' (estado posterior da linha já gravada) também é
        # decisão do revisor — o filtro do backfill inclui os dois.
        self._confirmacao_legada()
        CampoSugerido.objects.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='importado',
        )

        self._rodar_backfill()

        self.assertTrue(
            self._campo('/acts/0/tipo_sugerido').escolha_explicita,
        )
