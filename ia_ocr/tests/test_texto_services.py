"""Serviços de confirmação do texto OCR (issue #261 / I-4).

`confirmar_pagina` grava `texto_confirmado` + auditoria (quem/quando);
`editar_pagina` invalida a confirmação (página "editada" exige reconfirmação);
`confirmar_todas_paginas` é o bulk (só sem edição pendente);
`confirmar_texto` é a transição concluido → texto_confirmado ("Extrair campos").
Nenhuma atua fora do estado `concluido`. Os estados da página são derivados
dos campos que já existem desde a I-1 (sem migration).
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.estados import TransicaoInvalida
from ia_ocr.models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob,
    OcrJobTransicao, PaginaOcr,
)
from ia_ocr.services import EdicaoPendente, TextoNaoEditavel

from .factories import criar_job_concluido, criar_usuario


class EstadoDaPaginaTest(TestCase):
    def setUp(self):
        self.job = criar_job_concluido(textos=['alfa'])
        self.pagina = self.job.paginas.get(numero_pagina=1)

    def test_pagina_nova_nao_esta_confirmada(self):
        self.assertEqual(self.pagina.estado, ESTADO_NAO_CONFIRMADA)
        self.assertEqual(self.pagina.texto_exibido, 'alfa')
        self.assertFalse(self.pagina.tem_edicao)

    def test_pagina_com_confirmado_em_esta_confirmada(self):
        self.pagina.confirmado_em = timezone.now()
        self.pagina.texto_confirmado = 'alfa'

        self.assertEqual(self.pagina.estado, ESTADO_CONFIRMADA)

    def test_confirmacao_legada_sem_texto_confirmado_usa_o_texto_ocr(self):
        """Confirmação sem `texto_confirmado` (fixtures da I-1) segue válida."""
        self.pagina.confirmado_em = timezone.now()

        self.assertEqual(self.pagina.estado, ESTADO_CONFIRMADA)
        self.assertEqual(self.pagina.texto_exibido, 'alfa')
        self.assertFalse(self.pagina.tem_edicao)

    def test_texto_confirmado_sem_confirmado_em_e_editada(self):
        self.pagina.texto_confirmado = 'alfa corrigido'

        self.assertEqual(self.pagina.estado, ESTADO_EDITADA)
        self.assertEqual(self.pagina.texto_exibido, 'alfa corrigido')
        self.assertTrue(self.pagina.tem_edicao)


class ConfirmarPaginaTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(textos=['alfa', 'beta'])

    def test_grava_texto_confirmado_e_auditoria_de_quem_e_quando(self):
        antes = timezone.now()

        pagina, alterada = services.confirmar_pagina(self.job, 1, self.usuario)

        pagina.refresh_from_db()
        self.assertTrue(alterada)
        self.assertEqual(pagina.texto_ocr, 'alfa')
        self.assertEqual(pagina.texto_confirmado, 'alfa')
        self.assertEqual(pagina.confirmado_por, self.usuario)
        self.assertGreaterEqual(pagina.confirmado_em, antes)
        self.assertLessEqual(pagina.confirmado_em, timezone.now())
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_nao_toca_nas_outras_paginas(self):
        services.confirmar_pagina(self.job, 1, self.usuario)

        outra = self.job.paginas.get(numero_pagina=2)
        self.assertIsNone(outra.confirmado_em)
        self.assertIsNone(outra.texto_confirmado)

    def test_texto_editado_e_gravado_e_o_ocr_original_fica_preservado(self):
        pagina, _alterada = services.confirmar_pagina(
            self.job, 1, self.usuario, texto='alfa corrigido'
        )

        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_ocr, 'alfa')
        self.assertEqual(pagina.texto_confirmado, 'alfa corrigido')
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
        self.assertTrue(pagina.tem_edicao)

    def test_normaliza_quebra_de_linha_do_navegador(self):
        """O navegador envia CRLF; sem normalizar, toda página viraria 'editada'."""
        job = criar_job_concluido(textos=['linha 1\nlinha 2'])

        pagina, _alterada = services.confirmar_pagina(
            job, 1, self.usuario, texto='linha 1\r\nlinha 2'
        )

        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_confirmado, 'linha 1\nlinha 2')
        self.assertFalse(pagina.tem_edicao)

    def test_pagina_em_branco_e_confirmavel(self):
        pagina, _alterada = services.confirmar_pagina(
            self.job, 1, self.usuario, texto=''
        )

        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_confirmado, '')
        self.assertIsNotNone(pagina.confirmado_em)
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_reconfirmar_sem_mudanca_preserva_a_auditoria_original(self):
        primeiro = self.usuario
        segundo = criar_usuario()
        pagina, _alterada = services.confirmar_pagina(self.job, 1, primeiro)
        quando = timezone.now() - timedelta(days=1)
        PaginaOcr.objects.filter(pk=pagina.pk).update(confirmado_em=quando)

        _pagina, alterada = services.confirmar_pagina(self.job, 1, segundo)

        pagina.refresh_from_db()
        self.assertFalse(alterada)
        self.assertEqual(pagina.confirmado_por, primeiro)
        self.assertEqual(pagina.confirmado_em, quando)

    def test_reconfirmar_com_texto_novo_refaz_a_auditoria(self):
        segundo = criar_usuario()
        services.confirmar_pagina(self.job, 1, self.usuario)

        pagina, alterada = services.confirmar_pagina(
            self.job, 1, segundo, texto='alfa revisado'
        )

        pagina.refresh_from_db()
        self.assertTrue(alterada)
        self.assertEqual(pagina.texto_confirmado, 'alfa revisado')
        self.assertEqual(pagina.confirmado_por, segundo)

    def test_confirma_o_rascunho_salvo_quando_nao_recebe_texto(self):
        services.editar_pagina(self.job, 1, 'alfa rascunho')

        pagina, _alterada = services.confirmar_pagina(self.job, 1, self.usuario)

        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_confirmado, 'alfa rascunho')
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_recusa_job_fora_de_concluido_sem_gravar_nada(self):
        for status in (
            estados.PENDENTE, estados.EM_EXECUCAO, estados.FALHOU,
            estados.TEXTO_CONFIRMADO, estados.EXTRAIDO,
        ):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)

                with self.assertRaises(TextoNaoEditavel):
                    services.confirmar_pagina(self.job, 1, self.usuario)

                pagina = self.job.paginas.get(numero_pagina=1)
                self.assertIsNone(pagina.confirmado_em)
                self.assertIsNone(pagina.texto_confirmado)

    def test_pagina_inexistente_levanta_does_not_exist(self):
        with self.assertRaises(PaginaOcr.DoesNotExist):
            services.confirmar_pagina(self.job, 99, self.usuario)


class EditarPaginaTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(textos=['alfa', 'beta'])

    def test_editar_pagina_confirmada_marca_editada_e_zera_a_confirmacao(self):
        services.confirmar_pagina(self.job, 1, self.usuario)

        pagina, alterada = services.editar_pagina(
            self.job, 1, 'alfa corrigido'
        )

        pagina.refresh_from_db()
        self.assertTrue(alterada)
        self.assertEqual(pagina.estado, ESTADO_EDITADA)
        self.assertEqual(pagina.texto_confirmado, 'alfa corrigido')
        self.assertEqual(pagina.texto_ocr, 'alfa')
        self.assertIsNone(pagina.confirmado_em)
        self.assertIsNone(pagina.confirmado_por)

    def test_pagina_editada_exige_reconfirmacao_para_confirmar_o_texto(self):
        for numero in (1, 2):
            services.confirmar_pagina(self.job, numero, self.usuario)
        services.editar_pagina(self.job, 1, 'alfa corrigido')

        with self.assertRaises(TransicaoInvalida) as ctx:
            self.job.transicionar(estados.TEXTO_CONFIRMADO, usuario=self.usuario)
        self.assertEqual(ctx.exception.code, 'paginas_nao_confirmadas')

        services.confirmar_pagina(self.job, 1, self.usuario)
        self.job.transicionar(estados.TEXTO_CONFIRMADO, usuario=self.usuario)
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

    def test_editar_pagina_nao_confirmada_tambem_vira_editada(self):
        pagina, alterada = services.editar_pagina(
            self.job, 2, 'beta corrigido'
        )

        self.assertTrue(alterada)
        self.assertEqual(pagina.estado, ESTADO_EDITADA)
        self.assertIsNone(pagina.confirmado_em)

    def test_editar_sem_mudanca_nao_invalida_a_confirmacao(self):
        pagina, _alterada = services.confirmar_pagina(self.job, 1, self.usuario)

        _pagina, alterada = services.editar_pagina(self.job, 1, 'alfa')

        pagina.refresh_from_db()
        self.assertFalse(alterada)
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
        self.assertEqual(pagina.confirmado_por, self.usuario)

    def test_editar_normaliza_quebra_de_linha_do_navegador(self):
        job = criar_job_concluido(textos=['linha 1\nlinha 2'])

        _pagina, alterada = services.editar_pagina(
            job, 1, 'linha 1\r\nlinha 2'
        )

        self.assertFalse(alterada)
        self.assertEqual(job.paginas.get(numero_pagina=1).estado, ESTADO_NAO_CONFIRMADA)

    def test_recusa_job_fora_de_concluido(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        with self.assertRaises(TextoNaoEditavel):
            services.editar_pagina(self.job, 1, 'alfa corrigido')

        pagina = self.job.paginas.get(numero_pagina=1)
        self.assertIsNone(pagina.texto_confirmado)

    def test_pagina_inexistente_levanta_does_not_exist(self):
        with self.assertRaises(PaginaOcr.DoesNotExist):
            services.editar_pagina(self.job, 99, 'x')


class ConfirmarTodasPaginasTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(textos=['alfa', 'beta', 'gama'])

    def test_confirma_todas_as_pendentes_com_o_texto_do_ocr_e_auditoria(self):
        antes = timezone.now()

        total = services.confirmar_todas_paginas(self.job, self.usuario)

        self.assertEqual(total, 3)
        for pagina in self.job.paginas.all():
            self.assertEqual(pagina.texto_confirmado, pagina.texto_ocr)
            self.assertEqual(pagina.confirmado_por, self.usuario)
            self.assertGreaterEqual(pagina.confirmado_em, antes)
            self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_nao_transiciona_o_job(self):
        services.confirmar_todas_paginas(self.job, self.usuario)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_nao_refaz_auditoria_nem_texto_das_paginas_ja_confirmadas(self):
        outro = criar_usuario()
        services.confirmar_pagina(self.job, 1, outro, texto='alfa corrigido')
        original = self.job.paginas.get(numero_pagina=1)

        total = services.confirmar_todas_paginas(self.job, self.usuario)

        self.assertEqual(total, 2)
        pagina = self.job.paginas.get(numero_pagina=1)
        self.assertEqual(pagina.confirmado_por, outro)
        self.assertEqual(pagina.confirmado_em, original.confirmado_em)
        self.assertEqual(pagina.texto_confirmado, 'alfa corrigido')

    def test_recusa_quando_ha_pagina_editada_e_nao_confirma_nada(self):
        services.editar_pagina(self.job, 2, 'beta rascunho')

        with self.assertRaises(EdicaoPendente):
            services.confirmar_todas_paginas(self.job, self.usuario)

        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)
        self.assertEqual(
            self.job.paginas.get(numero_pagina=2).texto_confirmado, 'beta rascunho'
        )

    def test_pagina_confirmada_e_depois_editada_tambem_bloqueia(self):
        services.confirmar_pagina(self.job, 1, self.usuario)
        services.editar_pagina(self.job, 1, 'alfa mexida')

        with self.assertRaises(EdicaoPendente):
            services.confirmar_todas_paginas(self.job, self.usuario)

    def test_tudo_ja_confirmado_devolve_zero(self):
        services.confirmar_todas_paginas(self.job, self.usuario)

        self.assertEqual(services.confirmar_todas_paginas(self.job, self.usuario), 0)

    def test_recusa_job_fora_de_concluido(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        with self.assertRaises(TextoNaoEditavel):
            services.confirmar_todas_paginas(self.job, self.usuario)

        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)


class ConfirmarTextoTest(TestCase):
    """concluido → texto_confirmado ("Extrair campos →"): só com tudo confirmado."""

    def setUp(self):
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(textos=['alfa', 'beta'])

    def _confirmar_todas(self):
        for numero in (1, 2):
            services.confirmar_pagina(self.job, numero, self.usuario)

    def test_com_todas_confirmadas_transiciona_e_audita_o_usuario(self):
        self._confirmar_todas()

        services.confirmar_texto(self.job, self.usuario)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)
        transicao = self.job.transicoes.get(para_status=estados.TEXTO_CONFIRMADO)
        self.assertEqual(transicao.de_status, estados.CONCLUIDO)
        self.assertEqual(transicao.usuario, self.usuario)

    def test_com_pagina_pendente_recusa_e_nao_muda_o_estado(self):
        services.confirmar_pagina(self.job, 1, self.usuario)

        with self.assertRaises(TransicaoInvalida) as ctx:
            services.confirmar_texto(self.job, self.usuario)

        self.assertEqual(ctx.exception.code, 'paginas_nao_confirmadas')
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(
            OcrJobTransicao.objects.filter(
                ocr_job=self.job, para_status=estados.TEXTO_CONFIRMADO
            ).exists()
        )

    def test_com_pagina_editada_recusa_ate_reconfirmar(self):
        self._confirmar_todas()
        services.editar_pagina(self.job, 2, 'beta mexida')

        with self.assertRaises(TransicaoInvalida):
            services.confirmar_texto(self.job, self.usuario)

        services.confirmar_pagina(self.job, 2, self.usuario)
        services.confirmar_texto(self.job, self.usuario)
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

    def test_depois_de_texto_confirmado_o_texto_vira_somente_leitura(self):
        self._confirmar_todas()
        services.confirmar_texto(self.job, self.usuario)

        with self.assertRaises(TextoNaoEditavel):
            services.editar_pagina(self.job, 1, 'tarde demais')
        with self.assertRaises(TextoNaoEditavel):
            services.confirmar_pagina(self.job, 1, self.usuario, texto='tarde demais')

        self.assertEqual(self.job.paginas.get(numero_pagina=1).texto_confirmado, 'alfa')

    def test_job_que_ja_esta_em_texto_confirmado_nao_transiciona_de_novo(self):
        self._confirmar_todas()
        services.confirmar_texto(self.job, self.usuario)

        with self.assertRaises(TransicaoInvalida):
            services.confirmar_texto(self.job, self.usuario)
