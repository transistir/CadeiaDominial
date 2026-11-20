"""Parte 2 de 2 do corpo de ``RevisaoServicesTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_revisao_services.py``.
"""

"""Persistência transacional e finalização da revisão com dados sintéticos."""

from collections import Counter

from django.utils import timezone

from dominial.models import LancamentoTipo
from ia_ocr import estados, services, valores
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob
from ia_ocr.revisao import (
    pendencias,
)

from .factories import criar_usuario


class RevisaoServicesTestParte2:
    def test_trocar_para_tipo_com_cartorio_de_origem_cria_as_seis_linhas(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=True, requer_observacao=False,
        )

        self._confere_origem_completa_uma_vez('registro')

    def test_trocar_para_inicio_de_matricula_cria_as_seis_linhas(self):
        # Início de matrícula exige o cartório de origem mesmo com o flag
        # desligado na configuração (``_caminhos_do_tipo``).
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        LancamentoTipo.objects.create(
            tipo='inicio_matricula', requer_cartorio_origem=False,
            requer_observacao=False,
        )

        self._confere_origem_completa_uma_vez('inicio_matricula')

    def test_trocar_para_tipo_sem_origem_nao_cria_linhas_de_origem(self):
        # Averbação sem origem segue sem origem vazia: só o tipo que exige o
        # cartório de origem desmonta o bloco inteiro.
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )

        _salva, _versao, _partes, campos_novos = self._trocar_tipo('averbacao')

        self.assertEqual([c for c in campos_novos if '/origem/' in c], [])
        self.assertEqual(self._chaves_da_origem_no_banco(), Counter())

    def test_salvar_recusa_sugestao_acima_do_limite_na_linha_enviada(self):
        self._resolver_pendencias()
        CampoSugerido.objects.create(
            extracao=self.extracao,
            chave='/acts/0/area',
            raw='999999999.99 ha',
            normalized='999999999.99',
            tipo_valor='area',
            status_revisao='sugerido',
        )
        versao = services.versao_bloco(self.extracao)

        with self.assertRaises(valores.ValorInvalido) as contexto:
            services.salvar_bloco(
                self.extracao,
                {'/acts/0/area': {
                    'incluir': True, 'conferido': True,
                }},
                self.usuario, versao,
            )

        self.assertEqual(contexto.exception.chave, '/acts/0/area')
        self.assertEqual(services.versao_bloco(self.extracao), versao)

    def _criar_linha_acima_do_limite(self, chave):
        CampoSugerido.objects.create(
            extracao=self.extracao,
            chave=chave,
            raw='999999999.99 ha',
            normalized='999999999.99',
            tipo_valor='area',
            status_revisao='sugerido',
        )

    def test_save_corrige_uma_linha_mesmo_com_outra_acima_do_limite(self):
        self._resolver_pendencias()
        for chave in ('/acts/0/area', '/acts/1/area'):
            self._criar_linha_acima_do_limite(chave)
        versao = services.versao_bloco(self.extracao)

        services.salvar_bloco(
            self.extracao,
            {'/acts/0/area': {
                'incluir': True, 'conferido': True, 'valor': '100.00',
            }},
            self.usuario, versao,
        )

        limite = {
            item['chave'] for item in pendencias(self.extracao)
            if item['motivo'] == valores.MOTIVO_LIMITE
        }
        self.assertEqual(limite, {'/acts/1/area'})
        self.assertEqual(
            self.extracao.campos.get(
                chave='/acts/0/area',
            ).status_revisao,
            'editado',
        )

    def test_finalizacao_ainda_bloqueia_por_limite_intocado(self):
        self._resolver_pendencias()
        self._criar_linha_acima_do_limite('/acts/1/area')

        with self.assertRaises(services.RevisaoIncompleta) as contexto:
            services.finalizar_revisao(self.extracao, self.usuario)

        self.assertEqual(contexto.exception.pendencias, [{
            'chave': '/acts/1/area',
            'motivo': valores.MOTIVO_LIMITE,
            'bloqueante': True,
        }])
        self.extracao.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)

    def test_linha_descartada_acima_do_limite_nao_bloqueia_save(self):
        self.extracao.campos.filter(chave='/document/numero').update(
            normalized='X' * 51, status_revisao='descartado',
        )
        versao = services.versao_bloco(self.extracao)

        services.salvar_bloco(
            self.extracao,
            {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
            self.usuario, versao,
        )

        campo = self.extracao.campos.get(chave='/document/numero')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_ato_descartado_com_filho_acima_do_limite_nao_bloqueia_save(self):
        self.extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        CampoSugerido.objects.create(
            extracao=self.extracao,
            chave='/acts/0/numero_lancamento',
            raw='X' * 51,
            normalized='X' * 51,
            tipo_valor='texto',
            status_revisao='sugerido',
        )
        versao = services.versao_bloco(self.extracao)

        services.salvar_bloco(
            self.extracao,
            {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
            self.usuario, versao,
        )

        self.assertEqual(
            self.extracao.campos.get(chave='/acts/0').status_revisao,
            'descartado',
        )

    def test_finalizar_recusa_sugestao_acima_do_limite(self):
        self._resolver_pendencias()
        CampoSugerido.objects.create(
            extracao=self.extracao,
            chave='/acts/0/area',
            raw='999999999.99 ha',
            normalized='999999999.99',
            tipo_valor='area',
            status_revisao='sugerido',
        )

        with self.assertRaises(services.RevisaoIncompleta) as contexto:
            services.finalizar_revisao(self.extracao, self.usuario)

        self.assertEqual(contexto.exception.pendencias, [{
            'chave': '/acts/0/area',
            'motivo': valores.MOTIVO_LIMITE,
            'bloqueante': True,
        }])
        self.extracao.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)

    def test_salvar_depois_de_finalizada_recusa(self):
        self._resolver_pendencias()
        services.finalizar_revisao(self.extracao, self.usuario)
        versao = services.versao_bloco(self.extracao)

        for status in (estados.REVISADO, estados.EXTRAIDO, estados.IMPORTADO):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)
                with self.assertRaises(services.ExtracaoRecusada):
                    services.salvar_bloco(
                        self.extracao,
                        {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
                        self.usuario, versao,
                    )
                self.assertEqual(services.versao_bloco(self.extracao), versao)
                self.assertEqual(self.job.transicoes.count(), 1)

    def test_finalizar_com_pendencia_422_lista_pendencias(self):
        self._resolver_pendencias()
        carregada = ExtracaoSugerida.objects.prefetch_related('campos').get(
            pk=self.extracao.pk,
        )
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='sugerido', requer_revisao=True,
        )

        with self.assertRaises(services.RevisaoIncompleta) as contexto:
            services.finalizar_revisao(carregada, self.usuario)

        self.assertEqual(contexto.exception.code, 'revisao_incompleta')
        self.assertEqual(contexto.exception.pendencias, [{
            'chave': '/document/data', 'motivo': 'revisao_pendente',
            'bloqueante': True,
        }])
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)
        self.assertIsNone(self.extracao.finalizada_por)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())

    def test_finalizar_sem_pendencia_transiciona_e_audita(self):
        self._resolver_pendencias()
        antes = timezone.now()

        resultado = services.finalizar_revisao(self.extracao, self.usuario)

        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(resultado.pk, self.extracao.pk)
        self.assertEqual(resultado.finalizada_em, self.extracao.finalizada_em)
        self.assertGreaterEqual(self.extracao.finalizada_em, antes)
        self.assertLessEqual(self.extracao.finalizada_em, timezone.now())
        self.assertEqual(self.extracao.finalizada_por, self.usuario)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(resultado.ocr_job.status, estados.REVISADO)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.usuario, self.usuario)
        self.assertEqual(transicao.motivo, 'revisao_finalizada')

    def test_finalizar_duas_vezes_e_idempotente(self):
        self._resolver_pendencias()
        primeira = services.finalizar_revisao(self.extracao, self.usuario)
        transicao = self.job.transicoes.get()
        # O chamador retém a instância antiga, ainda sem finalizada_em.
        self.assertIsNone(self.extracao.finalizada_em)
        outro_usuario = criar_usuario()

        segunda = services.finalizar_revisao(self.extracao, outro_usuario)

        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(segunda.pk, primeira.pk)
        self.assertEqual(segunda.finalizada_em, primeira.finalizada_em)
        self.assertEqual(self.extracao.finalizada_em, primeira.finalizada_em)
        self.assertEqual(self.extracao.finalizada_por, self.usuario)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(self.job.transicoes.get().pk, transicao.pk)

    def test_finalizar_com_versao_atual_funciona(self):
        self._resolver_pendencias()
        versao = services.versao_bloco(self.extracao)

        finalizada = services.finalizar_revisao(
            self.extracao, self.usuario, versao_cliente=versao,
        )
        # Duplo clique: finalizar não muda o bloco, e o reenvio é idempotente.
        repetida = services.finalizar_revisao(
            self.extracao, self.usuario, versao_cliente=versao,
        )

        self.job.refresh_from_db()
        self.assertIsNotNone(finalizada.finalizada_em)
        self.assertEqual(finalizada.finalizada_por, self.usuario)
        self.assertEqual(repetida.finalizada_em, finalizada.finalizada_em)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(self.job.transicoes.count(), 1)
