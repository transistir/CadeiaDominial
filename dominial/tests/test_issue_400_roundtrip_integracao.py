"""
Issue #400 (v2) — round-trip REAL de edição: view → service → banco.

O textarea do navegador submete CRLF (``\\r\\n``), enquanto o serviço separa
blocos com ``\\n\\n``. Sem normalizar as quebras, o bloco
``[ANÁLISE — autor — data]`` volta colado ao texto documental num único
parágrafo: ``remover_analises`` não separa e ``buscar_keyword`` passa a ler o
texto do revisor — o badge nasce do texto do sistema, exatamente o que a issue
proíbe.

Diferente de ``test_issue_400_observacoes_analise.py`` (que monta o texto em
Python e usa ``SimpleNamespace``), aqui a escrita passa pelo test client: um
revert de ``lancamento_form_service``/``lancamento_criacao_service`` derruba
estes testes.
"""

import re

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import (Cartorios, Documento, DocumentoTipo, Imovel,
                             Lancamento, LancamentoTipo, Pessoas, TIs)
from dominial.services.keyword_alerta_service import buscar_keyword
from dominial.services.observacoes_analise import remover_analises
from dominial.tests.segregacao_fixtures import atribuir_tis

DATA = timezone.localdate().isoformat()
AUTOR = 'Fulano de Tal'
DOCUMENTAL = 'Área remanescente de 55 ha 69 a 85 ca'
ANALITICO = 'PENDENTE de certidão'
MARCADOR = f'[ANÁLISE — {AUTOR} — {DATA}]'


def _valor_do_textarea(html, nome):
    """Conteúdo do ``<textarea name=nome>`` — o que o navegador reenvia."""
    casamento = re.search(
        r'<textarea[^>]*\bname="%s"[^>]*>(.*?)</textarea>' % re.escape(nome),
        html,
        re.S,
    )
    return casamento.group(1) if casamento else ''


class Issue400RoundTripBase(TestCase):
    """Mesmo esqueleto das views reais; usuário COMUM com a TI atribuída."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='t400v2', password='t400v2pass',
            first_name='Fulano', last_name='de Tal',
        )
        cls.tis = TIs.objects.create(nome='TI #400v2', codigo='TI-400V2', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Proprietário #400v2')
        cls.cri = Cartorios.objects.create(
            nome='CRI de Ponta Porã', cns='CNS-400V2', cidade='Ponta Porã', estado='MS')
        cls.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis, nome='FAZENDA MADAMA', proprietario=cls.pessoa,
            matricula='T2540', tipo_documento_principal='transcricao', cartorio=cls.cri)
        atribuir_tis(cls.user, cls.tis)
        cls.doc = Documento.objects.create(
            imovel=cls.imovel, tipo=cls.tipo_transcricao, numero='T2540',
            data='2026-08-31', cartorio=cls.cri, livro='3H', folha='154')

    def setUp(self):
        self.client = Client()
        self.client.login(username='t400v2', password='t400v2pass')

    # -- POSTs -------------------------------------------------------------
    def url_novo(self):
        return reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            'documento_id': self.doc.id})

    def url_editar(self, lancamento):
        return reverse('editar_lancamento', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            'lancamento_id': lancamento.id})

    def _campos_comuns(self, observacoes):
        return {
            'cartorio': str(self.cri.id), 'cartorio_nome': self.cri.nome,
            'livro_documento': '3H', 'folha_documento': '154',
            'sigla_documento': self.doc.numero, 'tipo_lancamento': str(self.tipo_inicio.id),
            'numero_lancamento_simples': '', 'numero_lancamento': self.doc.numero,
            'sigla_matricula': self.doc.numero, 'documento_id': str(self.doc.id),
            'data': '1950-03-10',
            'transmitente_nome[]': ['Transmitente #400v2'], 'transmitente[]': [''],
            'adquirente_nome[]': ['Adquirente #400v2'], 'adquirente[]': [''],
            'forma_transacao': '', 'titulo_transacao': '', 'cartorio_transmissao_nome': '',
            'cartorio_transmissao': '', 'livro_transacao': '', 'folha_transacao': '',
            'data_transacao': '',
            'origem_completa[]': [''], 'cartorio_origem_nome[]': [''], 'cartorio_origem[]': [''],
            'livro_origem[]': [''], 'folha_origem[]': [''],
            'observacoes': observacoes, 'area': '',
        }

    def post_novo(self, observacoes, analise_texto=None):
        dados = self._campos_comuns(observacoes)
        if analise_texto is not None:
            dados['analise_texto'] = analise_texto
        return self.client.post(self.url_novo(), dados)

    def post_edicao(self, lancamento, observacoes, analise_texto=None, **extra):
        dados = self._campos_comuns(observacoes)
        dados['data'] = '1951-04-11'
        if analise_texto is not None:
            dados['analise_texto'] = analise_texto
        dados.update(extra)
        return self.client.post(self.url_editar(lancamento), dados)

    def criar_com_analise(self):
        response = self.post_novo(DOCUMENTAL, ANALITICO)
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])
        return Lancamento.objects.get(documento=self.doc)


class Issue400CriacaoPelaViewTest(Issue400RoundTripBase):
    """A criação real grava o marcador com autor e data — e só ele."""

    def test_formulario_oferece_a_acao_explicita_de_analise(self):
        html = self.client.get(self.url_novo()).content.decode()
        self.assertIn('name="analise_texto"', html)

    def test_criacao_grava_marcador_com_autor_e_data(self):
        lancamento = self.criar_com_analise()

        self.assertEqual(
            lancamento.observacoes,
            f'{DOCUMENTAL}\n\n{MARCADOR} {ANALITICO}\n[/ANÁLISE]',
        )

    def test_criacao_sem_analise_nao_prefixa_o_documental(self):
        response = self.post_novo(DOCUMENTAL)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            Lancamento.objects.get(documento=self.doc).observacoes, DOCUMENTAL)


class Issue400PreviewAutorTest(Issue400RoundTripBase):
    """O preview do formulário mostra o MESMO nome que o serviço grava."""

    def test_preview_usa_o_nome_completo_do_autor(self):
        html = self.client.get(self.url_novo()).content.decode()
        self.assertIn(f'[ANÁLISE — {AUTOR} — AAAA-MM-DD]', html)

    def test_sem_nome_completo_o_preview_usa_o_username(self):
        outro = User.objects.create_user(
            username='semNome', password='semNomePass', first_name='   ')
        atribuir_tis(outro, self.tis)
        self.client.login(username='semNome', password='semNomePass')

        html = self.client.get(self.url_novo()).content.decode()
        self.assertIn('[ANÁLISE — semNome — AAAA-MM-DD]', html)


class Issue400AutorSanitizadoTest(Issue400RoundTripBase):
    """#400 v4d: nome com ``[``/``]``/``—`` não pode derrubar a gravação.

    ``Maria [FUNAI]`` fazia ``nome_do_autor`` devolver o nome cru e
    ``marcador_analise`` levantar ``AnaliseSemAutor`` no save (500). O nome
    gravado sai sanitizado e o preview do formulário mostra o MESMO valor.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user.first_name = 'Maria'
        cls.user.last_name = '[FUNAI]'
        cls.user.save()

    def test_analise_de_usuario_com_colchetes_no_nome_e_gravada_com_autor_sanitizado(self):
        response = self.post_novo(DOCUMENTAL, ANALITICO)

        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])
        lancamento = Lancamento.objects.get(documento=self.doc)
        self.assertEqual(
            lancamento.observacoes,
            f'{DOCUMENTAL}\n\n[ANÁLISE — Maria FUNAI — {DATA}] {ANALITICO}'
            '\n[/ANÁLISE]',
        )

    def test_preview_mostra_o_autor_sanitizado(self):
        html = self.client.get(self.url_novo()).content.decode()

        self.assertIn('[ANÁLISE — Maria FUNAI — AAAA-MM-DD]', html)
        self.assertNotIn('[ANÁLISE — Maria [FUNAI]', html)


class Issue400RoundTripEdicaoTest(Issue400RoundTripBase):
    """MUST-FIX 1: o marcador sobrevive ao round-trip com CRLF do navegador.

    v4: o textarea leva SÓ o documental — o bloco analítico fica em área
    somente leitura e o servidor o reanexa a cada gravação.
    """

    def test_edicao_de_outro_campo_nao_perde_nem_duplica_a_analise(self):
        lancamento = self.criar_com_analise()

        # O navegador reenvia o textarea pré-preenchido COM CRLF.
        html = self.client.get(self.url_editar(lancamento)).content.decode()
        textarea = _valor_do_textarea(html, 'observacoes')
        self.assertNotIn(MARCADOR, textarea)
        self.assertEqual(textarea.strip(), DOCUMENTAL)
        # O bloco do banco aparece fora do textarea (somente leitura).
        self.assertIn(MARCADOR, html)
        self.assertIn(ANALITICO, html)

        response = self.post_edicao(
            lancamento, textarea.replace('\n', '\r\n'), data='1951-04-11')
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])

        lancamento.refresh_from_db()
        self.assertNotIn('\r', lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count(MARCADOR), 1)
        self.assertIn(f'{MARCADOR} {ANALITICO}', lancamento.observacoes)
        # O badge NÃO pode nascer da análise do revisor.
        self.assertIsNone(buscar_keyword(lancamento.observacoes))
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)

    def test_documental_com_palavra_chave_continua_gerando_badge(self):
        response = self.post_novo('Certidão pendente de averbação', ANALITICO)
        self.assertEqual(response.status_code, 302)
        lancamento = Lancamento.objects.get(documento=self.doc)

        resultado = buscar_keyword(lancamento.observacoes)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['label'], 'PENDENTE')

    def test_analise_digitada_na_edicao_e_gravada_com_marcador(self):
        lancamento = self.criar_com_analise()

        response = self.post_edicao(
            lancamento, DOCUMENTAL,
            analise_texto='Soma das áreas confere com o R.5.')
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])

        lancamento.refresh_from_db()
        self.assertIn(f'{MARCADOR} {ANALITICO}', lancamento.observacoes)
        self.assertIn(f'{MARCADOR} Soma das áreas confere com o R.5.',
                      lancamento.observacoes)
        self.assertTrue(lancamento.observacoes.startswith(DOCUMENTAL))

    def test_duas_edicoes_seguidas_nao_duplicam_nem_perdem_o_marcador(self):
        lancamento = self.criar_com_analise()

        for _ in range(2):
            html = self.client.get(self.url_editar(lancamento)).content.decode()
            textarea = _valor_do_textarea(html, 'observacoes')
            response = self.post_edicao(
                lancamento, textarea.replace('\n', '\r\n'))
            self.assertEqual(response.status_code, 302)
            lancamento.refresh_from_db()

        self.assertEqual(lancamento.observacoes.count(MARCADOR), 1)
        self.assertIsNone(buscar_keyword(lancamento.observacoes))


class Issue400ForjaDeAutorTest(Issue400RoundTripBase):
    """P1 #1 do Greptile: o POST documental não cria análise nem autoria."""

    FORJADO = f'[ANÁLISE — Outro revisor — 2026-11-25] aprovado'

    def test_marcador_forjado_no_textarea_nao_chega_ao_banco(self):
        response = self.post_novo(f'{DOCUMENTAL}\n\n{self.FORJADO}')
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])

        lancamento = Lancamento.objects.get(documento=self.doc)
        self.assertNotIn('[ANÁLISE', lancamento.observacoes)
        self.assertNotIn('Outro revisor', lancamento.observacoes)
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)

    def test_html_de_edicao_nao_exibe_a_autoria_forjada(self):
        self.post_novo(f'{DOCUMENTAL}\n\n{self.FORJADO}')
        lancamento = Lancamento.objects.get(documento=self.doc)

        html = self.client.get(self.url_editar(lancamento)).content.decode()

        self.assertNotIn('Outro revisor', html)
        self.assertNotIn('aprovado', html)

    def test_keyword_digitado_no_campo_documental_dispara_badge(self):
        response = self.post_novo(
            f'PENDENTE de certidão\n\n{self.FORJADO}')
        self.assertEqual(response.status_code, 302)

        lancamento = Lancamento.objects.get(documento=self.doc)
        resultado = buscar_keyword(lancamento.observacoes)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['label'], 'PENDENTE')
        self.assertNotIn('Outro revisor', lancamento.observacoes)

    def test_edicao_com_marcador_forjado_preserva_so_a_analise_do_banco(self):
        lancamento = self.criar_com_analise()

        response = self.post_edicao(
            lancamento, f'{DOCUMENTAL}\n\n{self.FORJADO}')
        self.assertEqual(response.status_code, 302)

        lancamento.refresh_from_db()
        self.assertNotIn('Outro revisor', lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count(MARCADOR), 1)


class Issue400AnaliseMultiParagrafoTest(Issue400RoundTripBase):
    """P1 #2 do Greptile: todos os parágrafos do revisor ficam no bloco."""

    ANALISE_2_PARAGRAFOS = 'Soma confere.\n\nPENDENTE de certidão'

    def test_analise_com_dois_paragrafos_nao_gera_badge(self):
        response = self.post_novo(DOCUMENTAL, self.ANALISE_2_PARAGRAFOS)
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])

        lancamento = Lancamento.objects.get(documento=self.doc)

        self.assertIsNone(buscar_keyword(lancamento.observacoes))
        self.assertIn('[/ANÁLISE]', lancamento.observacoes)
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)

    def test_segundo_paragrafo_nao_aparece_no_textarea_documental(self):
        self.post_novo(DOCUMENTAL, self.ANALISE_2_PARAGRAFOS)
        lancamento = Lancamento.objects.get(documento=self.doc)

        html = self.client.get(self.url_editar(lancamento)).content.decode()
        textarea = _valor_do_textarea(html, 'observacoes')

        self.assertEqual(textarea.strip(), DOCUMENTAL)
        # ...mas o revisor continua vendo a análise inteira na leitura.
        self.assertIn('PENDENTE de certidão', html)

    def test_edicao_posterior_nao_libera_o_segundo_paragrafo(self):
        self.post_novo(DOCUMENTAL, self.ANALISE_2_PARAGRAFOS)
        lancamento = Lancamento.objects.get(documento=self.doc)

        response = self.post_edicao(lancamento, DOCUMENTAL)
        self.assertEqual(response.status_code, 302)

        lancamento.refresh_from_db()
        self.assertIsNone(buscar_keyword(lancamento.observacoes))
        self.assertIn('PENDENTE de certidão', lancamento.observacoes)
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)
