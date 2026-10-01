"""
Regressões dos follow-ups da revisão r5 do PR #158 (área do formulário de
lançamento). Bugs pré-existentes:

- #159: herança pré-preenchia o campo de área visível com ``0`` — no submit o
  JS copiava visível→hidden e gravava ``0.0`` em vez de ``None``.
- #160: ``preservar_titulo`` era via de mão única — ``titulo`` nunca podia ser
  limpo deixando o bloco Transmissão vazio.
- #161: re-render de erro de NOVO lançamento não repunha as origens e o fim de
  cadeia digitados no POST.
- #162: ``traceback.format_exc()`` completo ia para ``messages.error`` visível
  ao usuário (info-leak).

Follow-ups da revisão Codex sobre o commit inicial:

- #160/finding 1: ``area`` faltava em ``_CAMPOS_BLOCO_TRANSMISSAO`` — averbação
  em transcrição com SÓ a área preenchida limpava o ``titulo``.
- #161/finding 2: ``_origens_separadas_do_post`` indexava os arrays
  ``*_fim_cadeia[]`` pela contagem de checkboxes marcados (``j``) em vez da
  posição da origem (``i``) — origens sem fim de cadeia desalinhavam tudo.
- #161/finding 3: ``_origens_separadas_do_post`` ignorava cartório/livro/folha
  no teste de "tem conteúdo" — uma linha só com esses campos era descartada.
- #162/finding 4: o caminho de exclusão (``excluir_lancamento``) também
  expunha ``str(e)`` ao usuário.

Rodada 2 da revisão:

- #159/rodada 2: cartório/livro/folha ficavam ``disabled`` nas linhas de fim de
  cadeia — some do POST, o array paralelo encolhe e as linhas seguintes herdam
  valores na posição errada. Agora vão ``readonly`` (continuam no POST).
- #162/rodada 2: ``removeOrigem`` não renumerava — o checkbox ``fim_cadeia[]``
  ficava com ``value`` furado. Agora o JS renumera o checkbox e o servidor
  também infere o fim de cadeia pelos arrays densos ``*_fim_cadeia[]``.

Rodada 3 da revisão:

- #162/rodada 3: só o REMOVER renumerava. O ADICIONAR
  (``adicionarOrigemSimples``/``adicionarOrigem``) não — remover a linha do meio
  e adicionar outra dava ``value`` duplicado no ``fim_cadeia[]``. Agora os dois
  caminhos chamam ``renumerarCheckboxesFimCadeia``; o servidor já tolera a
  colisão (teste de pertinência, nunca marca duas linhas).
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    OrigemFimCadeia,
    Pessoas,
    TIs,
)
from ..services.lancamento_campos_service import LancamentoCamposService
from ..services.lancamento_service import LancamentoService


class FormBugsBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="t159", password="t159pass")
        self.client = Client()
        self.client.login(username="t159", password="t159pass")

        self.tis = TIs.objects.create(nome="TI 159", etnia="Teste", estado="SP")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 159", cns="CNS159159", cidade="São Paulo"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        self.pessoa = Pessoas.objects.create(nome="Proprietário 159", cpf="15915915915")

        self.imovel = Imovel.objects.create(
            nome="Imóvel 159",
            matricula="99999",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )
        self.documento = Documento.objects.create(
            numero="99999",
            tipo=self.tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )
        # Já existe o lançamento "1" → herança liga `modo_edicao=True` e o
        # próximo POST com número "1" cai no re-render de erro (número duplicado).
        self.lancamento_existente = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            numero_lancamento="1",
            data="2020-01-01",
        )
        self.url = reverse("novo_lancamento", args=[self.tis.id, self.imovel.id])


class Issue159AreaHerancaTest(FormBugsBase):
    def test_get_com_heranca_nao_pre_preenche_area_com_zero(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("modo_edicao"))
        html = response.content.decode()

        # O campo visível de área deve vir VAZIO (não "0"), igual ao hidden
        # `name="area"`, para que um submit sem toque no campo grave `None`.
        self.assertRegex(html, r'id="area_transmissao"[^>]*value=""')
        self.assertNotRegex(html, r'id="area_transmissao"[^>]*value="0"')

    def test_submit_sem_tocar_area_grava_none(self):
        self.client.post(
            self.url,
            {
                "tipo_lancamento": str(self.tipo_registro.id),
                "numero_lancamento": "2",
                "numero_lancamento_simples": "2",
                "data": "2020-03-03",
                # JS copiaria o campo visível (que antes vinha "0") para o hidden;
                # simulamos o resultado correto: hidden vazio.
                "area": "",
            },
        )
        criado = Lancamento.objects.get(documento=self.documento, numero_lancamento="2")
        self.assertIsNone(criado.area)


class Issue161OrigensNoReRenderTest(FormBugsBase):
    def _post_duplicado(self, extra):
        payload = {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento": "1",  # duplicado → re-render de erro
            "numero_lancamento_simples": "1",
            "data": "2020-03-03",
        }
        payload.update(extra)
        return self.client.post(self.url, payload)

    def test_origens_digitadas_sobrevivem_ao_re_render(self):
        response = self._post_duplicado(
            {
                "origem_completa[]": "M123",
                "cartorio_origem_nome[]": "Cartório Origem X",
                "cartorio_origem[]": "",
                "livro_origem[]": "L10",
                "folha_origem[]": "F20",
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0]["texto"], "M123")
        self.assertEqual(origens[0]["tipo_origem"], "M")
        self.assertEqual(origens[0]["numero_origem"], "123")

        html = response.content.decode()
        self.assertRegex(html, r'id="numero_origem_0"[^>]*value="123"')
        self.assertRegex(html, r'value="Cartório Origem X"')
        self.assertRegex(html, r'id="livro_origem_0"[^>]*value="L10"')
        self.assertRegex(html, r'id="folha_origem_0"[^>]*value="F20"')

    def test_fim_de_cadeia_digitado_sobrevive_ao_re_render(self):
        response = self._post_duplicado(
            {
                "origem_completa[]": "Sem Origem::sem_origem",
                "cartorio_origem_nome[]": "",
                "cartorio_origem[]": "",
                "livro_origem[]": "",
                "folha_origem[]": "",
                "fim_cadeia[]": "0",
                "tipo_fim_cadeia[]": "sem_origem",
                "classificacao_fim_cadeia[]": "sem_origem",
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 1)
        self.assertTrue(origens[0]["fim_cadeia"])
        self.assertEqual(origens[0]["tipo_fim_cadeia"], "sem_origem")
        self.assertEqual(origens[0]["classificacao_fim_cadeia"], "sem_origem")

        html = response.content.decode()
        self.assertRegex(html, r'id="fim_cadeia_0"[^>]*checked')

    def test_sem_origens_no_post_mantem_fallback_em_branco(self):
        response = self._post_duplicado({})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["origens_separadas"], [])


class Issue162TracebackNaoVazaTest(FormBugsBase):
    def test_erro_inesperado_nao_expoe_traceback_ao_usuario(self):
        segredo = "RuntimeError em /opt/app/dominial/services/secreto.py"
        with patch.object(
            LancamentoService,
            "criar_lancamento_completo",
            side_effect=RuntimeError(segredo),
        ):
            response = self.client.post(
                self.url,
                {
                    "tipo_lancamento": str(self.tipo_registro.id),
                    "numero_lancamento": "7",
                    "numero_lancamento_simples": "7",
                    "data": "2020-03-03",
                },
            )

        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(msgs)
        self.assertTrue(any("Erro interno" in m for m in msgs))
        self.assertFalse(any("Traceback" in m for m in msgs))
        self.assertFalse(any(segredo in m for m in msgs))
        self.assertFalse(any("services/secreto.py" in m for m in msgs))


class Issue162ExclusaoTracebackNaoVazaTest(FormBugsBase):
    """finding 4: o caminho de exclusão também expunha `str(e)` ao usuário."""

    def test_erro_ao_excluir_nao_expoe_detalhe_do_erro(self):
        segredo = "IntegrityError em /opt/app/dominial/models/secreto.py"
        url = reverse(
            "excluir_lancamento",
            args=[self.tis.id, self.imovel.id, self.lancamento_existente.id],
        )
        with patch.object(Lancamento, "delete", side_effect=RuntimeError(segredo)):
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(msgs)
        self.assertTrue(any("Erro interno" in m for m in msgs))
        self.assertFalse(any(segredo in m for m in msgs))
        self.assertFalse(any("secreto.py" in m for m in msgs))


class Issue161OrigensFimCadeiaIndexTest(FormBugsBase):
    """finding 2/3: `_origens_separadas_do_post` no re-render de erro."""

    def _post_duplicado(self, extra):
        payload = {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento": "1",  # duplicado → re-render de erro
            "numero_lancamento_simples": "1",
            "data": "2020-03-03",
        }
        payload.update(extra)
        return self.client.post(self.url, payload)

    def test_fim_de_cadeia_so_na_segunda_de_duas_origens(self):
        # Antes: `j` (posição entre os marcados) lia a linha 0, devolvendo vazio.
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M222"],
                "cartorio_origem_nome[]": ["Cart A", "Cart B"],
                "cartorio_origem[]": ["", ""],
                "livro_origem[]": ["", ""],
                "folha_origem[]": ["", ""],
                "fim_cadeia[]": "1",
                "tipo_fim_cadeia[]": ["", "outra"],
                "classificacao_fim_cadeia[]": ["", "inconclusa"],
                "especificacao_fim_cadeia[]": ["", "Detalhe da 2a origem"],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)
        self.assertFalse(origens[0]["fim_cadeia"])
        self.assertTrue(origens[1]["fim_cadeia"])
        self.assertEqual(origens[1]["tipo_fim_cadeia"], "outra")
        self.assertEqual(origens[1]["classificacao_fim_cadeia"], "inconclusa")
        self.assertEqual(origens[1]["especificacao_fim_cadeia"], "Detalhe da 2a origem")

    def test_fim_de_cadeia_na_primeira_e_terceira_origens(self):
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M222", "M333"],
                "cartorio_origem_nome[]": ["A", "B", "C"],
                "cartorio_origem[]": ["", "", ""],
                "livro_origem[]": ["", "", ""],
                "folha_origem[]": ["", "", ""],
                "fim_cadeia[]": ["0", "2"],
                "tipo_fim_cadeia[]": ["sem_origem", "", "outra"],
                "classificacao_fim_cadeia[]": ["origem_lidima", "", "inconclusa"],
                "especificacao_fim_cadeia[]": ["", "", "Espec da 3a"],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 3)

        self.assertTrue(origens[0]["fim_cadeia"])
        self.assertEqual(origens[0]["tipo_fim_cadeia"], "sem_origem")
        self.assertEqual(origens[0]["classificacao_fim_cadeia"], "origem_lidima")

        self.assertFalse(origens[1]["fim_cadeia"])
        self.assertEqual(origens[1]["tipo_fim_cadeia"], "")

        self.assertTrue(origens[2]["fim_cadeia"])
        self.assertEqual(origens[2]["tipo_fim_cadeia"], "outra")
        self.assertEqual(origens[2]["classificacao_fim_cadeia"], "inconclusa")
        self.assertEqual(origens[2]["especificacao_fim_cadeia"], "Espec da 3a")

    def test_linha_so_com_cartorio_livro_folha_sobrevive(self):
        # Antes: sem `origem_completa`/`cartorio_nome` preenchidos, `tem_conteudo`
        # era False e a linha inteira era descartada no re-render de erro.
        response = self._post_duplicado(
            {
                "origem_completa[]": "",
                "cartorio_origem_nome[]": "",
                "cartorio_origem[]": str(self.cartorio.id),
                "livro_origem[]": "L7",
                "folha_origem[]": "F8",
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0]["cartorio_id"], str(self.cartorio.id))
        self.assertEqual(origens[0]["livro"], "L7")
        self.assertEqual(origens[0]["folha"], "F8")


class Issue159162RowIdentityRodada2Test(FormBugsBase):
    """Rodada 2: cada array paralelo do POST precisa ter exatamente uma entrada
    por linha de origem, em ordem — mesmo quando a linha é fim de cadeia (campos
    de cartório/livro/folha ``readonly``, não ``disabled``, para não sumirem do
    POST — #159) ou quando uma linha anterior foi removida (checkbox
    ``fim_cadeia[]`` renumerado, com fallback pelos arrays densos — #162)."""

    def _post_duplicado(self, extra):
        payload = {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento": "1",  # duplicado → re-render de erro
            "numero_lancamento_simples": "1",
            "data": "2020-03-03",
        }
        payload.update(extra)
        return self.client.post(self.url, payload)

    def test_linha_fim_cadeia_com_placeholders_nao_desalinha_a_seguinte(self):
        # #159: linha 0 = fim de cadeia. Cartório/livro/folha vêm VAZIOS (campos
        # readonly + limpos), mas PRESENTES no POST. Linha 1 = origem normal.
        # Com `disabled` esses campos sumiam do POST, o array encolhia e a
        # linha 1 herdava os valores na posição errada.
        response = self._post_duplicado(
            {
                "origem_completa[]": ["Sem Origem::sem_origem", "M222"],
                "cartorio_origem_nome[]": ["", "Cartório Real"],
                "cartorio_origem[]": ["", ""],
                "livro_origem[]": ["", "L99"],
                "folha_origem[]": ["", "F88"],
                "fim_cadeia[]": "0",
                "tipo_fim_cadeia[]": ["sem_origem", ""],
                "classificacao_fim_cadeia[]": ["sem_origem", ""],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)

        self.assertTrue(origens[0]["fim_cadeia"])
        self.assertEqual(origens[0]["tipo_fim_cadeia"], "sem_origem")
        self.assertEqual(origens[0]["cartorio_nome"], "")
        self.assertEqual(origens[0]["livro"], "")
        self.assertEqual(origens[0]["folha"], "")

        self.assertFalse(origens[1]["fim_cadeia"])
        self.assertEqual(origens[1]["texto"], "M222")
        self.assertEqual(origens[1]["cartorio_nome"], "Cartório Real")
        self.assertEqual(origens[1]["livro"], "L99")
        self.assertEqual(origens[1]["folha"], "F88")

        html = response.content.decode()
        self.assertRegex(html, r'id="livro_origem_1"[^>]*value="L99"')
        self.assertRegex(html, r'id="folha_origem_1"[^>]*value="F88"')

    def test_indices_renumerados_apos_remocao_de_linha_do_meio(self):
        # #162: shape que o fix de JS produz — a origem do meio foi removida e
        # o checkbox `fim_cadeia[]` foi renumerado para a posição atual ("1").
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M333"],
                "cartorio_origem_nome[]": ["Cart A", ""],
                "cartorio_origem[]": ["", ""],
                "livro_origem[]": ["", ""],
                "folha_origem[]": ["", ""],
                "fim_cadeia[]": "1",
                "tipo_fim_cadeia[]": ["", "outra"],
                "classificacao_fim_cadeia[]": ["", "inconclusa"],
                "especificacao_fim_cadeia[]": ["", "Espec sobrevivente"],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)

        self.assertFalse(origens[0]["fim_cadeia"])
        self.assertEqual(origens[0]["texto"], "M111")
        self.assertEqual(origens[0]["cartorio_nome"], "Cart A")

        self.assertTrue(origens[1]["fim_cadeia"])
        self.assertEqual(origens[1]["tipo_fim_cadeia"], "outra")
        self.assertEqual(origens[1]["classificacao_fim_cadeia"], "inconclusa")
        self.assertEqual(origens[1]["especificacao_fim_cadeia"], "Espec sobrevivente")

    def test_checkbox_fim_cadeia_com_value_obsoleto_ainda_recuperado(self):
        # #162 (defesa em profundidade): se o renumber do JS falhar e o checkbox
        # mantiver o `value` antigo ("2") da linha removida, o fim de cadeia
        # ainda é inferido pelos arrays densos `*_fim_cadeia[]` (posição 1).
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M333"],
                "cartorio_origem_nome[]": ["Cart A", ""],
                "cartorio_origem[]": ["", ""],
                "livro_origem[]": ["", ""],
                "folha_origem[]": ["", ""],
                "fim_cadeia[]": "2",
                "tipo_fim_cadeia[]": ["", "sem_origem"],
                "classificacao_fim_cadeia[]": ["", "sem_origem"],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)
        self.assertFalse(origens[0]["fim_cadeia"])
        self.assertTrue(origens[1]["fim_cadeia"])
        self.assertEqual(origens[1]["tipo_fim_cadeia"], "sem_origem")


class Issue160AreaNoBlocoTransmissaoTest(TestCase):
    """finding 1: `area` faltava em `_CAMPOS_BLOCO_TRANSMISSAO`, então uma
    averbação em transcrição com SÓ a área preenchida era tratada como bloco
    Transmissão vazio e limpava o `titulo` herdado."""

    def setUp(self):
        self.factory = RequestFactory()
        self.tis = TIs.objects.create(nome="TI 160", etnia="Teste", estado="SP")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 160", cns="CNS160160", cidade="São Paulo"
        )
        self.pessoa = Pessoas.objects.create(nome="Prop 160", cpf="16016016016")
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo="averbacao")

        self.imovel = Imovel.objects.create(
            nome="Imóvel 160",
            matricula="77777",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="transcricao",
            cartorio=self.cartorio,
        )
        self.doc_transcricao = Documento.objects.create(
            numero="77777",
            tipo=self.tipo_transcricao,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )

    def test_averbacao_transcricao_so_area_preserva_titulo(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_transcricao,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1",
            data="2020-02-02",
            titulo="Escritura Pública",
        )
        request = self.factory.post(
            "/",
            {
                "forma_averbacao": "Averbação de Área",
                "titulo_transacao": "",
                "area_transmissao": "123,45",
                "area": "123,45",
            },
        )
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertEqual(lancamento.titulo, "Escritura Pública")
        self.assertEqual(lancamento.area, 123.45)


class Issue162RenumerarAoAdicionarRodada3Test(FormBugsBase):
    """Rodada 3: `renumerarCheckboxesFimCadeia` só rodava no REMOVER. O caminho
    de ADICIONAR (`adicionarOrigemSimples` / `adicionarOrigem`) não renumerava —
    depois de remover a linha do meio e adicionar outra, o `value` da nova linha
    (índice de ID, com gap) colidia com o de uma linha sobrevivente e o POST
    saía com `fim_cadeia[]` duplicado. Agora os dois caminhos renumeram.

    Testes: (1) o shape que o JS corrigido produz — `fim_cadeia[]` contíguo,
    sem duplicata; (2) defesa em profundidade — se um `value` duplicado ainda
    chegar, o servidor não pode marcar DUAS linhas por colisão."""

    def _post_duplicado(self, extra):
        payload = {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento": "1",  # duplicado → re-render de erro
            "numero_lancamento_simples": "1",
            "data": "2020-03-03",
        }
        payload.update(extra)
        return self.client.post(self.url, payload)

    def test_post_apos_remover_e_adicionar_aponta_so_a_linha_marcada(self):
        # JS corrigido: de [0,1,2] o usuário removeu a linha 1 e adicionou uma
        # nova; o renumber no ADD deixa `fim_cadeia[]` = "2" (posição atual da
        # nova linha), sem duplicar o "1" de uma linha sobrevivente.
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M333", "M444"],
                "cartorio_origem_nome[]": ["Cart A", "Cart B", ""],
                "cartorio_origem[]": ["", "", ""],
                "livro_origem[]": ["", "", ""],
                "folha_origem[]": ["", "", ""],
                "fim_cadeia[]": "2",
                "tipo_fim_cadeia[]": ["", "", "outra"],
                "classificacao_fim_cadeia[]": ["", "", "inconclusa"],
                "especificacao_fim_cadeia[]": ["", "", "Espec da nova linha"],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 3)
        self.assertFalse(origens[0]["fim_cadeia"])
        self.assertFalse(origens[1]["fim_cadeia"])
        self.assertTrue(origens[2]["fim_cadeia"])
        self.assertEqual(origens[2]["tipo_fim_cadeia"], "outra")
        self.assertEqual(origens[2]["especificacao_fim_cadeia"], "Espec da nova linha")

    def test_value_duplicado_nao_marca_duas_linhas_no_re_render(self):
        # Defesa em profundidade: `fim_cadeia[]` = ["1","1"] (colisão) para as
        # linhas 0,1,2. Só a linha 1 pode ser fim de cadeia — a linha 2 exigiria
        # conteúdo nos arrays densos dela (não tem).
        response = self._post_duplicado(
            {
                "origem_completa[]": ["M111", "M222", "M333"],
                "cartorio_origem_nome[]": ["", "", ""],
                "cartorio_origem[]": ["", "", ""],
                "livro_origem[]": ["", "", ""],
                "folha_origem[]": ["", "", ""],
                "fim_cadeia[]": ["1", "1"],
                "tipo_fim_cadeia[]": ["", "outra", ""],
                "classificacao_fim_cadeia[]": ["", "inconclusa", ""],
            }
        )
        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 3)
        self.assertFalse(origens[0]["fim_cadeia"])
        self.assertTrue(origens[1]["fim_cadeia"])
        self.assertFalse(origens[2]["fim_cadeia"])

    def test_value_duplicado_nao_cria_dois_registros_no_save(self):
        # Mesma colisão, mas no caminho de PERSISTÊNCIA
        # (`_processar_campos_inicio_matricula`): `str(i) in fim_cadeia_indices`
        # é teste de pertinência, então "1","1" marca só a linha 1 — um único
        # OrigemFimCadeia, nunca dois.
        tipo_im = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=tipo_im,
            numero_lancamento="M99",
            data="2020-04-04",
        )
        request = RequestFactory().post(
            "/",
            {
                "origem_completa[]": ["M111", "M222", "M333"],
                "cartorio_origem_nome[]": ["", "", ""],
                "cartorio_origem[]": ["", "", ""],
                "livro_origem[]": ["", "", ""],
                "folha_origem[]": ["", "", ""],
                "fim_cadeia[]": ["1", "1"],
                "tipo_fim_cadeia[]": ["", "outra", ""],
                "classificacao_fim_cadeia[]": ["", "inconclusa", ""],
            },
        )
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        registros = OrigemFimCadeia.objects.filter(lancamento=lancamento)
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().indice_origem, 1)
