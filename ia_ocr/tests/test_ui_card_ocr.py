"""UI do card "Extrair texto com IA" na página de upload (issue #260 / I-3, fatia 2).

Cobertura de template/contexto: o card aparece só para PDFs, lista os
arquivos digitais e reflete o estado inicial do job mais recente do arquivo
(botão desabilitado com job ativo, "Tentar novamente" com falha, "Revisar
texto" como link para a tela de confirmação quando concluído — I-4 / #261 — e
desabilitado, com a explicação, nos estados já confirmados). O polling em si é
coberto pelo harness Node (ia_ocr/tests/js/ocr_card.test.js).

Asserções de atributo usam parse de HTML (``django.test.html``) — a ordem dos
atributos no template não quebra o teste (review #260, item I).
"""

import json

from django.contrib.auth.models import User
from django.templatetags.static import static
from django.test import TestCase
from django.test.html import Element, parse_html
from django.urls import reverse

from ia_ocr import services

from .factories import criar_documento_digital


def _atributos(elemento):
    """Dicionário nome → valor dos atributos de um elemento parseado."""
    return dict(elemento.attributes)


def _elementos(conteudo, nome_tag, presentes=(), valores=None):
    """Elementos `nome_tag` que têm todos os atributos em `presentes` e os
    valores de `valores`. A ordem dos atributos no HTML é irrelevante."""
    valores = valores or {}
    achados = []

    def visitar(no):
        if not isinstance(no, Element):
            return
        atributos = _atributos(no)
        if (
            no.name == nome_tag
            and all(nome in atributos for nome in presentes)
            and all(atributos.get(nome) == valor for nome, valor in valores.items())
        ):
            achados.append(no)
        for filho in no.children:
            visitar(filho)

    visitar(parse_html(conteudo))
    return achados


def _texto(elemento):
    """Texto direto de um elemento parseado (filhos str concatenados)."""
    return ''.join(filho for filho in elemento.children if isinstance(filho, str))


def _texto_de_estilos(conteudo):
    """Conteúdo textual de todos os <style> da página."""
    pedacos = []
    for estilo in _elementos(conteudo, 'style'):
        pedacos.extend(filho for filho in estilo.children if isinstance(filho, str))
    return '\n'.join(pedacos)


class CardOcrUploadTestCase(TestCase):
    """Cenário: dono atribuído à TI do documento, como em test_views_ocr_jobs."""

    @classmethod
    def setUpTestData(cls):
        cls.dono = User.objects.create_user(username='dono-ui', password='senha-dono')
        cls.arquivo = criar_documento_digital(upload_por=cls.dono)
        cls.imovel = cls.arquivo.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id
        cls.documento = cls.arquivo.documento

        from dominial.models import UserTI
        UserTI.objects.create(user=cls.dono, tis=cls.ti)

    def url_upload(self):
        return reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def url_criar(self):
        return reverse('criar_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
        })

    def pagina(self):
        self.client.force_login(self.dono)
        return self.client.get(self.url_upload())

    # Cenário base ------------------------------------------------------------

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

    def url_texto(self, job):
        return reverse('texto_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'job_id': job.job_id,
        })

    def test_card_job_concluido_habilita_revisar_texto_e_aponta_para_a_tela(self):
        """I-4 (#261): com o OCR concluído, "Revisar texto" é um link ativo
        para a tela de confirmação do texto do job; o botão desabilitado e o
        motivo "Disponível na I-4" saem de cena."""
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from ia_ocr.models import OcrJob
        OcrJob.objects.filter(pk=job.pk).update(status='concluido')

        resposta = self.pagina()
        conteudo = resposta.content.decode()

        links = _elementos(conteudo, 'a', presentes=('data-ocr-revisar-link',))
        self.assertEqual(len(links), 1)
        self.assertEqual(_atributos(links[0])['href'], self.url_texto(job))
        self.assertNotIn('hidden', _atributos(links[0]))
        self.assertIn('Revisar texto', _texto(links[0]))
        revisar = _elementos(conteudo, 'button', presentes=('data-ocr-revisar',))[0]
        self.assertIn('hidden', _atributos(revisar))
        motivo = _elementos(conteudo, 'small', presentes=('data-ocr-revisar-motivo',))[0]
        self.assertIn('hidden', _atributos(motivo))
        self.assertIn('hidden', _atributos(_elementos(conteudo, 'button', presentes=('data-ocr-disparo',))[0]))
        self.assertNotContains(resposta, 'Disponível na I-4')

    def test_card_com_texto_ja_confirmado_mantem_revisar_desabilitado_com_explicacao(self):
        from ia_ocr.models import OcrJob
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        for status in ('texto_confirmado', 'extraido', 'revisado', 'importado'):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=job.pk).update(status=status)

                conteudo = self.pagina().content.decode()

                revisar = _elementos(conteudo, 'button', presentes=('data-ocr-revisar',))[0]
                self.assertIn('disabled', _atributos(revisar))
                self.assertNotIn('hidden', _atributos(revisar))
                link = _elementos(conteudo, 'a', presentes=('data-ocr-revisar-link',))[0]
                self.assertIn('hidden', _atributos(link))
                motivo = _elementos(conteudo, 'small', presentes=('data-ocr-revisar-motivo',))[0]
                self.assertNotIn('hidden', _atributos(motivo))
                self.assertIn('Texto já confirmado', _texto(motivo))

    # Item C — retomada do polling depois de o corte de falhas desistir --------

    def test_card_tem_botao_atualizar_status_escondido(self):
        """#260-C: depois do corte de reconexão (10 min de falhas de rede, ou
        erro permanente) o usuário retoma o polling pelo botão "Atualizar
        status", que nasce escondido no card."""
        resposta = self.pagina()

        self.assertContains(resposta, 'Atualizar status')
        atualizar = _elementos(
            resposta.content.decode(), 'button', presentes=('data-ocr-atualizar', 'hidden')
        )
        self.assertEqual(len(atualizar), 1)

    # Item D — acessibilidade do estado assíncrono ------------------------------

    def test_badge_e_erro_anunciam_mudancas_para_leitores_de_tela(self):
        """#260-D: badge/estado e região de erro com role=status + aria-live."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        badge = _elementos(conteudo, 'span', presentes=('data-ocr-badge',))
        self.assertEqual(len(badge), 1)
        self.assertEqual(_atributos(badge[0]).get('role'), 'status')
        self.assertEqual(_atributos(badge[0]).get('aria-live'), 'polite')

        erros = _elementos(conteudo, 'small', presentes=('data-ocr-erro',))
        self.assertEqual(len(erros), 1)
        self.assertEqual(_atributos(erros[0]).get('role'), 'status')
        self.assertEqual(_atributos(erros[0]).get('aria-live'), 'polite')

    def test_regiao_viva_do_reconectando_e_expectativa_fora_de_aria_live(self):
        """#307 (rodada 2): "Reconectando…" é região viva própria — role=status
        + aria-live=polite, sempre no DOM, vazia e sem hidden (alternar hidden
        não é anunciado de forma confiável). A linha de expectativa, que o JS
        repinta a cada segundo, NÃO tem aria-live nem role — e nasce vazia,
        porque o texto é da constante do JS."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        expectativas = _elementos(conteudo, 'small', presentes=('data-ocr-expectativa',))
        self.assertEqual(len(expectativas), 1)
        atributos = _atributos(expectativas[0])
        self.assertNotIn('aria-live', atributos)
        self.assertNotIn('role', atributos)
        self.assertEqual(_texto(expectativas[0]), '')

        reconectando = _elementos(conteudo, 'small', presentes=('data-ocr-reconectando',))
        self.assertEqual(len(reconectando), 1)
        atributos = _atributos(reconectando[0])
        self.assertEqual(atributos.get('role'), 'status')
        self.assertEqual(atributos.get('aria-live'), 'polite')
        self.assertNotIn('hidden', atributos)
        self.assertEqual(_texto(reconectando[0]), '')

    def test_expectativa_nasce_escondida_no_template(self):
        """#307 (rodada 3): a linha de expectativa nasce com `hidden` — o JS
        revela e preenche a linha só com job ativo; sem job ela fica escondida
        (o texto é da constante do JS, nunca do template)."""
        resposta = self.pagina()

        expectativas = _elementos(
            resposta.content.decode(), 'small', presentes=('data-ocr-expectativa', 'hidden')
        )
        self.assertEqual(len(expectativas), 1)

    def test_card_com_job_carrega_criado_em(self):
        """#307: o card com job carrega data-ocr-criado-em com o isoformat do
        job — é o início do contador de tempo decorrido antes do 1º poll."""
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)

        cards = _elementos(
            self.pagina().content.decode(), 'div', presentes=('data-ocr-card', 'data-ocr-criado-em'),
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(_atributos(cards[0])['data-ocr-criado-em'], job.criado_em.isoformat())

    def test_card_sem_job_nao_tem_criado_em(self):
        """#307: sem job o card não tem data-ocr-criado-em — o JS começa a
        contar do início do polling."""
        cards = _elementos(self.pagina().content.decode(), 'div', presentes=('data-ocr-card',))
        self.assertEqual(len(cards), 1)
        self.assertNotIn('data-ocr-criado-em', _atributos(cards[0]))

    def test_seta_do_card_e_decorativa_para_leitores_de_tela(self):
        """#260-D: todo `▶` do card fica em <span aria-hidden="true">."""
        resposta = self.pagina()
        conteudo = resposta.content.decode()

        setas = _elementos(conteudo, 'span', presentes=('aria-hidden',), valores={'aria-hidden': 'true'})
        com_setas = [span for span in setas if '▶' in _texto(span)]
        self.assertEqual(len(com_setas), 2)  # no h2 do card e no botão de disparo

    def test_motivo_do_revisar_desabilitado_e_percebivel(self):
        """#260-D: o motivo de "Revisar texto" estar desabilitado é texto
        visível, ligado ao botão por aria-describedby (title não é alcançável
        por teclado). Desde a I-4 isso só vale após a confirmação do texto."""
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from ia_ocr.models import OcrJob
        OcrJob.objects.filter(pk=job.pk).update(status='texto_confirmado')

        resposta = self.pagina()
        conteudo = resposta.content.decode()

        revisar = _elementos(conteudo, 'button', presentes=('data-ocr-revisar',))[0]
        descrito_por = _atributos(revisar).get('aria-describedby')
        self.assertTrue(descrito_por)

        motivos = _elementos(conteudo, 'small', presentes=('data-ocr-revisar-motivo',))
        self.assertEqual(len(motivos), 1)
        self.assertEqual(_atributos(motivos[0]).get('id'), descrito_por)
        self.assertNotIn('hidden', _atributos(motivos[0]))
        self.assertIn('Texto já confirmado', _texto(motivos[0]))

        # Fora dos estados com texto, o motivo acompanha o botão e some.
        OcrJob.objects.filter(pk=job.pk).update(status='pendente')
        resposta = self.pagina()
        conteudo = resposta.content.decode()
        motivos = _elementos(conteudo, 'small', presentes=('data-ocr-revisar-motivo',))
        self.assertEqual(len(motivos), 1)
        self.assertIn('hidden', _atributos(motivos[0]))

    # #284 — o JS do card é estático e a página precisa carregá-lo ----------------

    def test_pagina_inclui_o_estatico_do_js_do_card(self):
        """#284: o JS do card saiu do template para static/dominial/js/
        ocr_card.js. Os testes de HTML olham só o HTML inicial e o teste Node
        lê o arquivo direto do disco: sem esta asserção, apagar o <script src>
        mataria o card com a suíte verde."""
        resposta = self.pagina()

        scripts = _elementos(
            resposta.content.decode(),
            'script',
            valores={'src': static('dominial/js/ocr_card.js')},
        )
        self.assertEqual(
            len(scripts), 1,
            'a página precisa carregar dominial/js/ocr_card.js uma única vez',
        )
