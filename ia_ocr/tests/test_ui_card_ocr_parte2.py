"""Segunda parte dos testes do card OCR, migrada verbatim."""

from django.templatetags.static import static

from ia_ocr import services

from .test_ui_card_ocr_base import _atributos, _elementos, _texto


class CardOcrUploadTestCaseParte2:
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
