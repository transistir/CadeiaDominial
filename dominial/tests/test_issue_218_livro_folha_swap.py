"""Issue #218 — Livro↔Folha invertidos no banco (doc 3879 / T2540, imóvel 488).

Nenhum caminho do servidor inverte livro↔folha de entrada correta (guardas).
O defeito original: a correção digitada no Novo Lançamento era DESCARTADA EM
SILÊNCIO quando o documento já tinha livro/folha ≠ '0' (regra pétrea #138).
Estado pós-fix: Livro/Folha já definidos ficam readonly no formulário; um POST
divergente segue sem sobrescrever o banco, mas emite aviso; na edição de
lançamento os campos ficam sempre travados (o update não os persiste) e o link
"Corrigir em Editar Documento" aponta para o imóvel DONO do documento.
"""
import re
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.contrib.messages import constants as message_constants
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dominial.views.documento_views import excluir_documento
from dominial.models import (Cartorios, Documento, DocumentoTipo, Imovel,
                             Lancamento, LancamentoTipo, Pessoas, TIs)


class _HiddenInputsDoFormImportacao(HTMLParser):
    """(name, value) dos <input> do form que posta em `importar_duplicata`."""
    def __init__(self, action):
        super().__init__()
        self.action, self.dentro, self.campos = action, False, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and attrs.get('action') == self.action:
            self.dentro = True
        elif tag == 'input' and self.dentro and attrs.get('name'):
            self.campos.append((attrs['name'], attrs.get('value') or ''))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.dentro = False


def _tag_input(html, name):
    match = re.search(r'<input\b[^>]*\bname="%s"[^>]*>' % re.escape(name), html, re.S)
    return match.group(0) if match else ''


class Issue218Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='t218', password='t218pass')
        cls.tis = TIs.objects.create(nome='TI #218', codigo='TI-218', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Proprietário #218')
        cls.cri = Cartorios.objects.create(nome='CRI de Ponta Porã', cns='CNS-218',
                                           cidade='Ponta Porã', estado='MS')
        cls.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        cls.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        cls.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        cls.tipo_registro = LancamentoTipo.objects.create(tipo='registro')
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis, nome='FAZENDA MADAMA', proprietario=cls.pessoa,
            matricula='T2789', tipo_documento_principal='transcricao', cartorio=cls.cri)
        cls.doc_t2789 = Documento.objects.create(
            imovel=cls.imovel, tipo=cls.tipo_transcricao, numero='T2789',
            data='2026-08-31', cartorio=cls.cri, livro='3H', folha='200')

    def setUp(self):
        self.client = Client()
        self.client.login(username='t218', password='t218pass')
        # Estado de 31/08: criado por _criar_documento_automatico_com_cartorio.
        self.doc = Documento.objects.create(
            imovel=self.imovel, tipo=self.tipo_transcricao, numero='T2540',
            data=timezone.localdate(), data_presumida=True, cartorio=self.cri,
            livro='0', folha='0',
            origem='Criado automaticamente a partir de origem: T2540',
            observacoes=('Documento criado automaticamente ao identificar origem "T2540" '
                         'no lançamento T2789. Cartório da origem: CRI de Ponta Porã. '
                         'Livro: não informado, Folha: não informada'))

    def url_novo(self):
        return reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id, 'documento_id': self.doc.id})

    def post_lancamento(self, tipo, livro_documento, folha_documento, **extra):
        """Campos que o navegador envia para transcrição; *_transacao/*_origem
        vazios, como em 12386/12387."""
        dados = {
            'cartorio': str(self.cri.id), 'cartorio_nome': self.cri.nome,
            'livro_documento': livro_documento, 'folha_documento': folha_documento,
            'sigla_documento': self.doc.numero, 'tipo_lancamento': str(tipo.id),
            'numero_lancamento_simples': '', 'numero_lancamento': self.doc.numero,
            'sigla_matricula': self.doc.numero, 'documento_id': str(self.doc.id),
            'data': '1950-03-10',
            'transmitente_nome[]': ['Transmitente #218'], 'transmitente[]': [''],
            'adquirente_nome[]': ['Adquirente #218'], 'adquirente[]': [''],
            'forma_transacao': '', 'titulo_transacao': '', 'cartorio_transmissao_nome': '',
            'cartorio_transmissao': '', 'livro_transacao': '', 'folha_transacao': '',
            'data_transacao': '',
            'origem_completa[]': [''], 'cartorio_origem_nome[]': [''], 'cartorio_origem[]': [''],
            'livro_origem[]': [''], 'folha_origem[]': [''],
            'observacoes': '', 'area': '',
        }
        dados.update(extra)
        return self.client.post(self.url_novo(), dados)

    def post_averbacao(self, livro_documento, folha_documento):
        return self.post_lancamento(
            self.tipo_averbacao, livro_documento, folha_documento,
            numero_lancamento_simples='1', numero_lancamento='AV1 T2540',
            forma_averbacao='Retificação')

    def criar_lancamento_existente(self):
        return Lancamento.objects.create(documento=self.doc, tipo=self.tipo_inicio,
                                         numero_lancamento='T2540', data='1950-03-10')

    def livro_folha(self):
        self.doc.refresh_from_db()
        return self.doc.livro, self.doc.folha


class Issue218GuardasSemTrocaTest(Issue218Base):
    """GREEN: nenhum caminho inverte livro↔folha de entrada correta."""

    def test_criacao_direta_grava_livro_e_folha_sem_troca(self):
        response = self.post_lancamento(self.tipo_inicio, '3H', '154')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.livro_folha(), ('3H', '154'))

    @override_settings(DUPLICATA_VERIFICACAO_ENABLED=True)
    def test_fluxo_duplicata_reemite_e_grava_sem_troca(self):
        vizinho = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Imóvel vizinho', proprietario=self.pessoa,
            matricula='T100', tipo_documento_principal='transcricao', cartorio=self.cri)
        Documento.objects.create(imovel=vizinho, tipo=self.tipo_transcricao, numero='T100',
                                 data='2026-01-01', cartorio=self.cri, livro='3A', folha='12')

        tela = self.post_lancamento(self.tipo_inicio, '3H', '154', **{
            'origem_completa[]': ['T100'], 'cartorio_origem_nome[]': [self.cri.nome],
            'cartorio_origem[]': [str(self.cri.id)]})
        self.assertEqual(tela.status_code, 200)
        self.assertTemplateUsed(tela, 'dominial/duplicata_importacao.html')
        self.assertEqual(self.livro_folha(), ('0', '0'))

        url_importar = reverse('importar_duplicata', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id, 'documento_id': self.doc.id})
        parser = _HiddenInputsDoFormImportacao(url_importar)
        parser.feed(tela.content.decode())
        self.assertEqual(dict(parser.campos)['livro_documento'], '3H')
        self.assertEqual(dict(parser.campos)['folha_documento'], '154')

        post = {}
        for nome, valor in parser.campos:
            post.setdefault(nome, []).append(valor)
        response = self.client.post(url_importar, post)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lancamento.objects.filter(documento=self.doc).exists())
        self.assertEqual(self.livro_folha(), ('3H', '154'))

    def test_edicao_do_documento_grava_sem_troca_e_corrige_inversao(self):
        self.doc.livro, self.doc.folha = '154', '3H'
        self.doc.save()
        url = reverse('editar_documento', kwargs={
            'documento_id': self.doc.id, 'tis_id': self.tis.id, 'imovel_id': self.imovel.id})
        response = self.client.post(url, {
            'numero': self.doc.numero, 'tipo': str(self.tipo_transcricao.id),
            'data': '2026-08-31', 'cartorio': self.cri.nome, 'cartorio_id': str(self.cri.id),
            'livro': '3H', 'folha': '154', 'origem': self.doc.origem,
            'observacoes': self.doc.observacoes})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.livro_folha(), ('3H', '154'))

    def test_erro_de_validacao_nao_grava_nada_no_documento(self):
        self.criar_lancamento_existente()  # número duplicado → falha antes de gravar
        response = self.post_lancamento(self.tipo_inicio, '3H', '154')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.livro_folha(), ('0', '0'))

    def test_segundo_lancamento_nao_sobrescreve_valor_correto(self):
        self.post_lancamento(self.tipo_inicio, '3H', '154')
        self.post_averbacao('154', '3H')
        self.assertEqual(self.livro_folha(), ('3H', '154'))


class Issue218ReproducaoTest(Issue218Base):
    """Correção divergente: regra pétrea preservada, sem descarte silencioso."""

    def preparar_documento_ja_invertido(self):
        # Banco ANTES do POST do print: 154/3H gravado por POST anterior.
        self.doc.livro, self.doc.folha = '154', '3H'
        self.doc.save()
        self.criar_lancamento_existente()

    def test_reproducao_print_correto_e_banco_invertido(self):
        # Print correto na tela; banco inalterado (regra pétrea) + aviso.
        self.preparar_documento_ja_invertido()
        form = self.client.get(self.url_novo()).content.decode()
        self.assertIn('value="154"', _tag_input(form, 'livro_documento'))
        self.assertIn('value="3H"', _tag_input(form, 'folha_documento'))

        response = self.post_averbacao('3H', '154')  # print: Folha do Documento = 154
        self.assertEqual(response.status_code, 302)
        self.assertIn('✅ Lançamento criado com sucesso!',
                      [str(m) for m in get_messages(response.wsgi_request)])
        # Regra pétrea: o lançamento não sobrescreve; o banco fica inalterado e o
        # descarte deixa de ser silencioso (aviso coberto no teste de divergência).
        self.assertEqual(self.livro_folha(), ('154', '3H'))

    def test_novo_lancamento_exibe_livro_folha_ja_definidos_como_readonly(self):
        self.preparar_documento_ja_invertido()
        form = self.client.get(self.url_novo()).content.decode()
        self.assertIn('readonly', _tag_input(form, 'livro_documento'))
        self.assertIn('readonly', _tag_input(form, 'folha_documento'))

    def test_divergencia_ignorada_gera_aviso_e_preserva_regra_petrea(self):
        self.preparar_documento_ja_invertido()
        response = self.post_averbacao('3H', '154')
        self.assertEqual(self.livro_folha(), ('154', '3H'))
        avisos = [str(m) for m in get_messages(response.wsgi_request)
                  if m.level == message_constants.WARNING]
        self.assertEqual(len(avisos), 1, 'mensagens: %r' % avisos)
        self.assertIn('Livro gravado "154", informado "3H"', avisos[0])
        self.assertIn('Folha gravada "3H", informado "154"', avisos[0])
        self.assertIn('Editar Documento', avisos[0])

    def test_divergencia_nao_acusa_falso_positivo_com_espaco_no_legado(self):
        self.doc.livro, self.doc.folha = '3H ', '154'
        self.doc.save()
        self.criar_lancamento_existente()
        response = self.post_averbacao('3H', '154')
        avisos = [m for m in get_messages(response.wsgi_request)
                  if m.level == message_constants.WARNING]
        self.assertEqual(avisos, [])


class Issue218PlaceholderZeroTest(Issue218Base):
    """'0' (não informado) não pré-preenche nem vence o form_data."""

    def test_placeholder_zero_nao_aparece_como_valor_no_formulario(self):
        form = self.client.get(self.url_novo()).content.decode()
        self.assertNotIn('value="0"', _tag_input(form, 'livro_documento'))
        self.assertNotIn('value="0"', _tag_input(form, 'folha_documento'))

    def test_rerender_de_erro_preserva_livro_folha_digitados(self):
        self.criar_lancamento_existente()
        html = self.post_lancamento(self.tipo_inicio, '3H', '154').content.decode()
        self.assertIn('value="3H"', _tag_input(html, 'livro_documento'))
        self.assertIn('value="154"', _tag_input(html, 'folha_documento'))


class Issue218EdicaoLancamentoTest(Issue218Base):
    """Blocker B1: edição de lançamento não pode exigir campos que o update ignora."""

    def url_editar(self, lancamento):
        return reverse('editar_lancamento', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            'lancamento_id': lancamento.id})

    def test_edicao_com_documento_zero_nao_deixa_livro_folha_vazios_e_required(self):
        lancamento = self.criar_lancamento_existente()
        response = self.client.get(self.url_editar(lancamento))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for nome in ('livro_documento', 'folha_documento'):
            tag = _tag_input(html, nome)
            self.assertNotIn('required', tag, tag)
            self.assertIn('readonly', tag, tag)
            self.assertIn('tabindex="-1"', tag, tag)

    def test_edicao_exibe_link_para_editar_documento(self):
        lancamento = self.criar_lancamento_existente()
        html = self.client.get(self.url_editar(lancamento)).content.decode()
        self.assertIn('Corrigir em Editar Documento', html)

    def test_post_de_edicao_nao_perde_dados_e_retorna_sucesso(self):
        lancamento = self.criar_lancamento_existente()
        response = self.client.post(self.url_editar(lancamento), {
            'tipo_lancamento': str(self.tipo_inicio.id), 'numero_lancamento': 'T2540',
            'numero_lancamento_simples': '', 'data': '1951-04-11',
            'cartorio': str(self.cri.id), 'cartorio_nome': self.cri.nome,
            'livro_documento': '', 'folha_documento': '',
            'sigla_documento': 'T2540', 'sigla_matricula': 'T2540',
            'documento_id': str(self.doc.id),
            'transmitente_nome[]': ['Transmitente #218'], 'transmitente[]': [''],
            'adquirente_nome[]': ['Adquirente #218'], 'adquirente[]': [''],
            'origem_completa[]': [''], 'cartorio_origem_nome[]': [''],
            'cartorio_origem[]': [''], 'livro_origem[]': [''], 'folha_origem[]': [''],
            'observacoes': 'editado', 'area': ''})
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        lancamento.refresh_from_db()
        self.assertEqual(str(lancamento.data), '1951-04-11')
        self.assertEqual(lancamento.observacoes, 'editado')
        self.assertEqual(self.livro_folha(), ('0', '0'))


class Issue218LinkImovelDonoTest(Issue218Base):
    """Blocker B2: o link de correção usa o imóvel DONO do documento compartilhado."""

    def test_link_em_documento_compartilhado_aponta_para_imovel_dono(self):
        self.doc.livro, self.doc.folha = '154', '3H'
        self.doc.save()
        lancamento_dono = self.criar_lancamento_existente()

        outra_ti = TIs.objects.create(nome='Outra TI #218', codigo='TI-218B', etnia='Teste')
        importador = Imovel.objects.create(
            terra_indigena_id=outra_ti, nome='Importador', proprietario=self.pessoa,
            matricula='M999', tipo_documento_principal='matricula', cartorio=self.cri)
        doc_importador = Documento.objects.create(
            imovel=importador, tipo=self.tipo_matricula, numero='M999',
            data='2026-01-01', cartorio=self.cri, livro='1', folha='1')
        # bulk_create: evita o signal criar o documento da origem automaticamente.
        Lancamento.objects.bulk_create([Lancamento(
            documento=doc_importador, tipo=self.tipo_inicio, data='2026-01-02',
            origem='T2540', cartorio_origem=self.cri)])

        url = reverse('editar_lancamento', kwargs={
            'tis_id': outra_ti.id, 'imovel_id': importador.id,
            'lancamento_id': lancamento_dono.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        esperado = reverse('editar_documento', kwargs={
            'documento_id': self.doc.id, 'tis_id': self.tis.id, 'imovel_id': self.imovel.id})
        self.assertIn('href="%s"' % esperado, response.content.decode())
        self.assertEqual(self.client.get(esperado).status_code, 200)


class Issue218RedirectsDocumentoTest(Issue218Base):
    """Redirects pós-gravação (commit 0d53fbb5): rotas existentes."""

    def test_editar_documento_redireciona_para_documento_detalhado(self):
        url = reverse('editar_documento', kwargs={
            'documento_id': self.doc.id, 'tis_id': self.tis.id, 'imovel_id': self.imovel.id})
        response = self.client.post(url, {
            'numero': self.doc.numero, 'tipo': str(self.tipo_transcricao.id),
            'data': '2026-08-31', 'cartorio': self.cri.nome, 'cartorio_id': str(self.cri.id),
            'livro': '3H', 'folha': '154', 'origem': self.doc.origem,
            'observacoes': self.doc.observacoes})
        self.assertRedirects(response, reverse('documento_detalhado', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id, 'documento_id': self.doc.id}),
            fetch_redirect_response=False)

    def test_excluir_documento_redireciona_para_cadeia_dominial(self):
        # `excluir_documento` não tem rota em urls.py: chamada direta da view.
        request = RequestFactory().post('/excluir-documento/')
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = excluir_documento(
            request, tis_id=self.tis.id, imovel_id=self.imovel.id, documento_id=self.doc.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('cadeia_dominial', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id}))
        self.assertFalse(Documento.objects.filter(id=self.doc.id).exists())
