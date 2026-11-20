"""Primeira parte dos testes do card OCR, migrada verbatim."""

import json

from ia_ocr import services

from .test_ui_card_ocr_base import _atributos, _elementos, _texto_de_estilos


class CardOcrUploadTestCaseParte1:
    def test_card_ocr_aparece_para_pdf(self):
        resposta = self.pagina()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Extrair texto com IA')
        self.assertContains(resposta, self.arquivo.nome_original)
        # URL de disparo do job disponível para o JS
        self.assertContains(resposta, self.url_criar())
        # Nota informativa: atalho do texto embutido (I-2)
        self.assertContains(resposta, 'texto embutido')

    def test_card_ocr_nao_aparece_para_imagem(self):
        self.arquivo.tipo_mime = 'image/png'
        self.arquivo.save()

        resposta = self.pagina()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'Extrair texto com IA')

    # Item A — regra CSS escopada que faz `hidden` vencer o CSS de autor ------

    def test_regra_hidden_escopada_esta_no_html_depois_do_css_de_autor(self):
        """#260-A: `.btn` (base.css) sobrepõe o `[hidden]` do user-agent; a
        regra escopada do card precisa existir na página e vir depois do
        CSS de autor para valer no cascade."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        estilos = _texto_de_estilos(conteudo)
        self.assertIn('[data-ocr-card] [hidden]', estilos)
        self.assertIn('display: none !important', estilos)
        self.assertLess(
            conteudo.index('dominial/css/base.css'),
            conteudo.index('[data-ocr-card] [hidden]'),
            'a regra escopada precisa carregar depois de base.css',
        )

    def test_card_sem_job_estados_iniciais_escondidos(self):
        """#260-A: sem job, só o disparo aparece; erro, retry e revisar saem
        com `hidden` — que a regra escopada garante visívelmente escondido."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        disparos = _elementos(conteudo, 'button', presentes=('data-ocr-disparo',))
        self.assertEqual(len(disparos), 1)
        self.assertNotIn('hidden', _atributos(disparos[0]))
        self.assertNotIn('disabled', _atributos(disparos[0]))

        self.assertEqual(len(_elementos(conteudo, 'small', presentes=('data-ocr-erro', 'hidden'))), 1)
        self.assertEqual(len(_elementos(conteudo, 'button', presentes=('data-ocr-retry', 'hidden'))), 1)
        self.assertEqual(len(_elementos(conteudo, 'button', presentes=('data-ocr-revisar', 'hidden'))), 1)
        self.assertEqual(len(_elementos(conteudo, 'small', presentes=('data-ocr-revisar-motivo', 'hidden'))), 1)

    # Item F — única fonte dos estados, injetada pelo contexto da view ---------

    def test_contexto_expoe_listas_de_estado_de_ia_ocr_estados(self):
        """#260-F: a view injeta as listas de `ia_ocr.estados` para o template."""
        resposta = self.pagina()

        self.assertEqual(resposta.context['status_ativos'], ['pendente', 'em_execucao'])
        self.assertEqual(
            resposta.context['status_com_texto'],
            ['concluido', 'texto_confirmado', 'extraido', 'revisado', 'importado'],
        )
        # Só `concluido` ainda aceita revisão do texto (tela da I-4).
        self.assertEqual(resposta.context['status_revisaveis'], ['concluido'])

    def test_template_e_js_nao_repetem_listas_de_estado(self):
        """#260-F: nem if por substring no template, nem lista duplicada no
        JS — o card recebe as listas via data-* em JSON."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        # Antigo if por substring no template...
        self.assertNotContains(resposta, "job.status not in '")
        # ...e listas duplicadas no JS.
        self.assertNotContains(resposta, 'STATUS_ATIVOS')
        self.assertNotContains(resposta, 'STATUS_COM_TEXTO')
        # Listas chegando ao JS via data-* em JSON no container do card,
        # parseáveis e iguais às da view (review #260, item I).
        cards = _elementos(
            conteudo,
            'div',
            presentes=(
                'data-ocr-card', 'data-status-ativos', 'data-status-com-texto',
                'data-status-revisaveis',
            ),
        )
        self.assertEqual(len(cards), 1)
        atributos = _atributos(cards[0])
        self.assertEqual(
            json.loads(atributos['data-status-ativos']),
            resposta.context['status_ativos'],
        )
        self.assertEqual(
            json.loads(atributos['data-status-com-texto']),
            resposta.context['status_com_texto'],
        )
        self.assertEqual(
            json.loads(atributos['data-status-revisaveis']),
            resposta.context['status_revisaveis'],
        )

    # Item I — asserções tolerantes à ordem de atributos ------------------------

    def test_card_sem_job_mostra_botao_de_disparo_habilitado(self):
        resposta = self.pagina()

        disparos = _elementos(resposta.content.decode(), 'button', presentes=('data-ocr-disparo',))
        self.assertEqual(len(disparos), 1)
        self.assertNotIn('disabled', _atributos(disparos[0]))

    def test_card_com_job_ativo_botao_desabilitado_e_badge_com_status(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from django.urls import reverse as rev
        url_status = rev('status_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
            'job_id': job.job_id,
        })

        resposta = self.pagina()
        conteudo = resposta.content.decode()

        disparos = _elementos(conteudo, 'button', presentes=('data-ocr-disparo',))
        self.assertEqual(len(disparos), 1)
        self.assertIn('disabled', _atributos(disparos[0]))
        self.assertNotIn('hidden', _atributos(disparos[0]))
        self.assertContains(resposta, url_status)
        self.assertContains(resposta, job.get_status_display())
        # Fora desses estados: erro, retry e revisar escondidos (#260-A).
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'small', presentes=('data-ocr-erro',))[0]))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'button', presentes=('data-ocr-retry',))[0]))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'button', presentes=('data-ocr-revisar',))[0]))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'a', presentes=('data-ocr-revisar-link',))[0]))

    def test_card_job_falhou_mostra_tentar_novamente_e_motivo(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from ia_ocr.models import OcrJob
        OcrJob.objects.filter(pk=job.pk).update(
            status='falhou',
            erro_codigo='SERVICE_UNAVAILABLE',
            erro_mensagem='fila do serviço OCR cheia',
        )

        resposta = self.pagina()
        conteudo = resposta.content.decode()

        self.assertContains(resposta, 'Tentar novamente')
        self.assertContains(resposta, 'fila do serviço OCR cheia')
        retry = _elementos(conteudo, 'button', presentes=('data-ocr-retry',))[0]
        self.assertNotIn('hidden', _atributos(retry))
        erro = _elementos(conteudo, 'small', presentes=('data-ocr-erro',))[0]
        self.assertNotIn('hidden', _atributos(erro))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'button', presentes=('data-ocr-disparo',))[0]))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'button', presentes=('data-ocr-revisar',))[0]))
