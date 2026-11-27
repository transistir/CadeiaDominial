"""Regressão #388: cartório de origem com nome não cadastrado não pode ser criado."""

from unittest import mock

from dominial.models import Cartorios, Lancamento
from ia_ocr.revisao_ato.bloqueios import (
    MENSAGEM_CARTORIO_ORIGEM_NAO_CADASTRADO,
)

from .payloads_extracao import payload_registro
from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase,
    post_do_html,
)


class RevisaoCartorioOrigemNaoCadastradoTest(RevisaoFormularioBase):
    def _abrir_com_origem(self, nome_cartorio):
        """Uma extração de um ato cujo cartório de origem é ``nome_cartorio``."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': {
                **self._campo(nome_cartorio, 'CRI de Guaíra'),
                'match_sugerido': {'cartorio_id': None, 'candidatos': []},
            },
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def _post_de_origens(self, origens, nomes, ids=None):
        """GET do ato + POST com as origens informadas, alinhadas por posição."""
        pagina = self.client.get(self.url_ato(0))
        self.assertEqual(pagina.status_code, 200)
        post = post_do_html(pagina)
        total = len(origens)
        post['origem_completa[]'] = list(origens)
        post['cartorio_origem_nome[]'] = list(nomes)
        post['cartorio_origem[]'] = list(ids) if ids is not None else [''] * total
        post['livro_origem[]'] = [''] * total
        post['folha_origem[]'] = [''] * total
        return post

    def _assert_bloqueio_da_origem(self, resposta, nome):
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            MENSAGEM_CARTORIO_ORIGEM_NAO_CADASTRADO.format(nome=nome),
            '\n'.join(self.mensagens(resposta)),
        )

    def test_cartorio_origem_fantasma_nao_e_criado_e_ato_nao_e_salvo(self):
        nome_fantasma = "CRI Fantasma Teste 388"
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_fantasma).exists())
        self._abrir_com_origem(nome_fantasma)

        # POST como o navegador faria, com observações próprias para provar preservação
        texto_obs = "Observação de teste digitada pelo usuário"
        dados_post = post_do_html(self.client.get(self.url_ato(0)), observacoes=texto_obs)
        dados_post['fim_cadeia[]'] = ['0']
        dados_post['origem_completa[]'] = ['Destacamento Público: Gleba X']
        dados_post['tipo_lancamento'] = str(self.tipo_inicio.pk)

        resposta_post = self.client.post(self.url_ato(0), dados_post)

        self.assertEqual(resposta_post.status_code, 200)
        self.assertFalse(
            Cartorios.objects.filter(nome__iexact=nome_fantasma).exists(),
            f"Cartório '{nome_fantasma}' não deveria ter sido criado no banco!"
        )
        self.assertEqual(Lancamento.objects.count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')
        html = resposta_post.content.decode()
        self.assertIn(texto_obs, html)
        self._assert_bloqueio_da_origem(resposta_post, nome_fantasma)

    def test_cartorio_origem_nao_cadastrado_bloqueia_no_post_e_preserva_observacoes(self):
        nome_fantasma = "CRI Outro Fantasma 388"
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_fantasma).exists())
        self._abrir_com_origem(nome_fantasma)

        pagina_get = self.client.get(self.url_ato(0))
        self.assertEqual(pagina_get.status_code, 200)

        texto_obs = "Observações teste normal"
        dados_post = post_do_html(pagina_get, observacoes=texto_obs)

        resposta_post = self.client.post(self.url_ato(0), dados_post)

        self.assertEqual(resposta_post.status_code, 200)
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_fantasma).exists())
        self.assertEqual(Lancamento.objects.count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')
        html = resposta_post.content.decode()
        self.assertIn(texto_obs, html)
        self._assert_bloqueio_da_origem(resposta_post, nome_fantasma)

    def test_cartorio_origem_cadastrado_por_id_salva_sem_bloqueio(self):
        cartorio = self._cartorio('CRI Cadastrado Com ID')
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': {
                **self._campo(cartorio.nome, 'CRI de Guaíra'),
                'match_sugerido': {'cartorio_id': cartorio.pk, 'candidatos': []},
            },
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=cartorio,
        )

        cartorios_antes = Cartorios.objects.count()
        pagina_get = self.client.get(self.url_ato(0))
        dados_post = post_do_html(pagina_get)

        resposta_post = self.client.post(self.url_ato(0), dados_post)
        self.assertRedirects(resposta_post, self.url_documento(), fetch_redirect_response=False)
        self.assertEqual(Lancamento.objects.count(), 1)
        # Em registro o cartório da origem vive na linha estruturada; o campo
        # ``lancamento.cartorio_origem`` é do início de matrícula (help_text).
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.origens_estruturadas.get().cartorio, cartorio)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)

    def test_cartorio_origem_cadastrado_por_nome_fim_cadeia_salva_sem_bloqueio(self):
        cartorio = self._cartorio('CRI Cadastrado Previamente')
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': {
                **self._campo(cartorio.nome, 'CRI de Guaíra'),
                'match_sugerido': {'cartorio_id': None, 'candidatos': []},
            },
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        pagina_get = self.client.get(self.url_ato(0))
        dados_post = post_do_html(pagina_get)
        dados_post['fim_cadeia[]'] = ['0']
        dados_post['origem_completa[]'] = ['Destacamento Público: Gleba X']
        dados_post['tipo_lancamento'] = str(self.tipo_inicio.pk)

        resposta_post = self.client.post(self.url_ato(0), dados_post)
        self.assertRedirects(resposta_post, self.url_documento(), fetch_redirect_response=False)
        self.assertEqual(Lancamento.objects.count(), 1)
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.cartorio_origem, cartorio)

    def test_cartorio_origem_vazio_salva_sem_bloqueio(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        pagina_get = self.client.get(self.url_ato(0))
        dados_post = post_do_html(pagina_get)

        resposta_post = self.client.post(self.url_ato(0), dados_post)
        self.assertRedirects(resposta_post, self.url_documento(), fetch_redirect_response=False)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_cartorio_origem_com_caixa_diferente_ja_cadastrado_salva(self):
        """O service usa ``iexact``: diferença só de caixa não bloqueia.

        Nome sem id só passa pelo service quando a origem é fim de cadeia (a
        validação manual exige id para origem comum); o caminho de fim de
        cadeia é o que resolve o cartório por nome.
        """
        cartorio = self._cartorio('CRI Caixa Alta 388')
        cartorios_antes = Cartorios.objects.count()
        self._abrir_com_origem(cartorio.nome)

        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        post['fim_cadeia[]'] = ['0']
        post['origem_completa[]'] = ['Destacamento Público: Gleba X']
        post['cartorio_origem[]'] = ['']
        post['cartorio_origem_nome[]'] = ['cri caixa alta 388']
        post['tipo_lancamento'] = str(self.tipo_inicio.pk)

        resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.cartorio_origem, cartorio)

    def test_cartorio_origem_com_dois_cadastros_de_mesmo_nome_bloqueia(self):
        """``get(nome__iexact=...)`` estouraria com mais de um cadastro."""
        nome = 'CRI Homonimo 388'
        Cartorios.objects.create(nome=nome, cns='CNS-HOMONIMO-1')
        Cartorios.objects.create(nome=nome, cns='CNS-HOMONIMO-2')
        cartorios_antes = Cartorios.objects.count()
        self._abrir_com_origem(nome)

        post = self._post_de_origens(['M42.718'], [nome])
        resposta = self.client.post(self.url_ato(0), post)

        self._assert_bloqueio_da_origem(resposta, nome)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)

    def test_segunda_origem_fantasma_bloqueia_o_ato_inteiro_sem_criar_nada(self):
        cadastrado = self._cartorio('CRI Primeira Origem 388')
        fantasma = 'CRI Segunda Origem Fantasma 388'
        cartorios_antes = Cartorios.objects.count()
        self._abrir_com_origem(cadastrado.nome)

        post = self._post_de_origens(
            ['M42.718', 'M99.999'], [cadastrado.nome, fantasma],
        )
        resposta = self.client.post(self.url_ato(0), post)

        self._assert_bloqueio_da_origem(resposta, fantasma)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)

    def test_cartorio_origem_com_id_invalido_ou_inexistente_bloqueia_sem_500(self):
        """O service tenta o id antes do nome: inválido estoura, inexistente desvia."""
        fantasma = 'CRI Fantasma Com ID Ruim 388'
        cadastrado = self._cartorio('CRI Com Nome Cadastrado 388')
        cartorios_antes = Cartorios.objects.count()
        self._abrir_com_origem(fantasma)

        # Nome fantasma e nome cadastrado: com id preenchido o service nunca
        # chega na resolução por nome que salvaria o segundo caso.
        cenarios = (
            ('abc', fantasma),
            ('999999', fantasma),
            ('abc', cadastrado.nome),
            ('999999', cadastrado.nome),
        )
        for id_invalido, nome in cenarios:
            with self.subTest(id=id_invalido, nome=nome):
                post = self._post_de_origens(
                    ['M42.718'], [nome], ids=[id_invalido],
                )
                resposta = self.client.post(self.url_ato(0), post)

                self._assert_bloqueio_da_origem(resposta, nome)
                self.assertEqual(Lancamento.objects.count(), 0)
                self.assertEqual(Cartorios.objects.count(), cartorios_antes)

    def test_cartorio_origem_com_espaco_extra_nao_casa_e_bloqueia(self):
        """O service consulta o nome cru: espaço sobrando criaria duplicado."""
        cartorio = self._cartorio('CRI Sem Espaco 388')
        self._abrir_com_origem(cartorio.nome)
        cartorios_antes = Cartorios.objects.count()

        post = self._post_de_origens(['M42.718'], [f'{cartorio.nome} '])
        resposta = self.client.post(self.url_ato(0), post)

        self._assert_bloqueio_da_origem(resposta, cartorio.nome)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)

    def test_caminho_de_duplicata_tambem_bloqueia_origem_fantasma(self):
        """``salvar_ato`` com ``apos_importacao=True`` não pula os bloqueios.

        A importação da cadeia roda antes, mas o ato ainda passa por
        ``bloqueios_do_post`` dentro de ``salvar_ato``: o cartório de origem
        fantasma não pode ser criado nem por esse caminho (#388).
        """
        nome_fantasma = 'CRI Fantasma Duplicata 388'
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_fantasma).exists())
        self._abrir_com_origem(nome_fantasma)
        cartorios_antes = Cartorios.objects.count()

        post = self._post_de_origens(['Destacamento Público: Gleba Y'], [nome_fantasma])
        post['tipo_lancamento'] = str(self.tipo_inicio.pk)

        with mock.patch(
            'ia_ocr.views.revisar_extras.LancamentoDuplicataService.'
            'processar_importacao_duplicata',
            return_value={'sucesso': True, 'erros': []},
        ):
            resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, self.url_ato(0))
        mensagens = self.mensagens(resposta)
        self.assertEqual(Cartorios.objects.count(), cartorios_antes)
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_fantasma).exists())
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertIn(
            MENSAGEM_CARTORIO_ORIGEM_NAO_CADASTRADO.format(nome=nome_fantasma),
            '\n'.join(mensagens),
        )
