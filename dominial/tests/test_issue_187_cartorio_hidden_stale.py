"""Issue #187 — hidden `cartorio_origem_${index}` stale quando o operador
edita o nome do cartório (review Codex do PR #186).

Relato: em `configurarMAnterior` (static/dominial/js/origem_simples.js), o
campo de nome do cartório só registrava `keyup`/`blur` → `agendarMAnterior`.
Ao editar o nome SEM passar pelo autocomplete (ex.: escolheu 'Cartório X',
apagou e digitou 'Cartório Y'), a busca da M anterior disparava com o
`cartorio_id` antigo (X) enquanto o campo exibia 'Cartório Y' — o badge
renderizava informação do cartório errado, enganando a decisão de
'mesmo TI'/'outro TI'/'não consta'.

Fix: registrar também `input`, que limpa o hidden ANTES de agendar a busca.
Sem `cartorio_id`, `atualizarMAnterior` aborta e esconde o badge (guard do
P2 #185, já coberto por test_issue_167.GreptileP2RaceAbortTest).

Decisão de design documentada (ver testes abaixo):
- A seleção de sugestão NÃO dispara `input` — `selectCartorioSuggestion`
  (lancamento_form.js) seta `input.value`/`hidden.value` por atribuição
  direta, e a spec DOM não dispara evento em atribuição programática. Logo o
  listener `input` nunca apaga o ID recém-escolhido.
- `keyup` permanece registrado: a seleção via teclado (Enter) seta o hidden
  no `keydown`; o `keyup` subsequente reagenda a busca com o ID novo. Ele não
  reintroduz o stale porque, para teclas que mudam o valor, `input` dispara
  ANTES de `keyup` (ordem: keydown → input → keyup) e já limpou o hidden.

Sem infra de teste JS no repo (débito #202 F2), seguimos o precedente do
#168/#167: testes Django que leem o arquivo fonte e afirmam o comportamento
via pattern-matching.
"""
import os
import re

from django.test import TestCase


class LimpaHiddenStaleAoEditarNomeTest(TestCase):
    """O bloco do cartorioNome em `configurarMAnterior` deve registrar
    `input` que limpa o hidden antes de agendar; `blur` e `keyup` seguem."""

    JS_PATH = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'static', 'dominial', 'js', 'origem_simples.js',
    )

    def setUp(self):
        with open(self.JS_PATH, encoding='utf-8') as f:
            self.js_src = f.read()

    def _funcao_configurarMAnterior(self):
        match = re.search(
            r"function configurarMAnterior\(index\) \{(.*?)\n\}",
            self.js_src,
            re.DOTALL,
        )
        assert match is not None, (
            'Função configurarMAnterior não encontrada em origem_simples.js'
        )
        return match.group(1)

    def _bloco_cartorio_nome(self):
        corpo = self._funcao_configurarMAnterior()
        match = re.search(
            r"if \(cartorioNome\) \{(.*?)\n    \}",
            corpo,
            re.DOTALL,
        )
        assert match is not None, (
            'Bloco `if (cartorioNome)` não encontrado em configurarMAnterior'
        )
        return match.group(1)

    def test_configurarMAnterior_resolve_o_hidden_do_index(self):
        """A função precisa acessar o hidden `cartorio_origem_${index}` para
        poder limpá-lo — não apenas o campo de nome visível."""
        corpo = self._funcao_configurarMAnterior()
        self.assertIn(
            "getElementById(`cartorio_origem_${index}`)",
            corpo,
            'configurarMAnterior deve resolver o hidden cartorio_origem_'
            '{index} (o template literal `cartorio_origem_nome_${index}` do '
            'campo visível não satisfaz esta checagem)',
        )

    def test_cartorio_nome_registra_listener_input(self):
        """BUG #187: edição manual do nome precisa disparar limpeza do hidden.

        `input` cobre teclado, colar e autofill — `keyup` não cobre colar."""
        bloco = self._bloco_cartorio_nome()
        self.assertIn(
            "cartorioNome.addEventListener('input'",
            bloco,
            "campo de nome do cartório deve registrar listener 'input' "
            "(além de keyup/blur) para reagir a qualquer edição do valor",
        )

    def test_listener_input_limpa_o_hidden_antes_de_agendar(self):
        """BUG #187 (núcleo do fix): dentro do listener `input`, o hidden
        `cartorio_origem_` é zerado ANTES da chamada a agendarMAnterior.

        A ordem importa: agendarMAnterior só agenda — a leitura do hidden
        acontece 300ms depois, em atualizarMAnterior, mas limpar antes de
        agendar documenta a intenção e protege contra uma futura leitura
        síncrona."""
        bloco = self._bloco_cartorio_nome()
        listener = re.search(
            r"addEventListener\('input',\s*\(\)\s*=>\s*\{(.*?)\}\s*\);",
            bloco,
            re.DOTALL,
        )
        assert listener is not None, (
            "listener 'input' do cartorioNome não encontrado (teste irmão "
            "test_cartorio_nome_registra_listener_input falhou primeiro?)"
        )
        corpo = listener.group(1)

        pos_limpeza = corpo.find("cartorioHidden.value = ''")
        self.assertGreaterEqual(
            pos_limpeza,
            0,
            "listener 'input' deve zerar o hidden (cartorioHidden.value "
            "= '') enquanto o operador edita o nome",
        )
        pos_agendar = corpo.find('agendarMAnterior(index)')
        self.assertGreaterEqual(
            pos_agendar,
            0,
            "listener 'input' deve continuar agendando a busca da M anterior",
        )
        self.assertLess(
            pos_limpeza,
            pos_agendar,
            'a limpeza do hidden deve vir ANTES do agendamento da busca',
        )

    def test_listener_blur_permanece_registrado(self):
        """Guard de regressão: `blur` reagenda a busca — é ele que atualiza o
        badge após a seleção de sugestão via clique (que não dispara nem
        `input` nem `keyup`)."""
        bloco = self._bloco_cartorio_nome()
        self.assertIn(
            "cartorioNome.addEventListener('blur'",
            bloco,
            "listener 'blur' do cartorioNome não deve ser removido pelo fix "
            "#187",
        )

    def test_listener_keyup_permanece_para_selecao_via_teclado(self):
        """Guard de regressão + documentação do design: `keyup` permanece
        porque a seleção de sugestão via teclado (Enter) seta o hidden no
        `keydown` (selectCartorioSuggestion) — sem `keyup`, o badge da
        seleção via teclado só atualizaria no blur.

        `keyup` não reintroduz o stale #187: teclas que mudam o valor disparam
        `input` ANTES de `keyup` (ordem da spec: keydown → input → keyup), e o
        listener `input` já limpou o hidden."""
        bloco = self._bloco_cartorio_nome()
        self.assertIn(
            "cartorioNome.addEventListener('keyup'",
            bloco,
            "listener 'keyup' do cartorioNome deve permanecer para reagir à "
            "seleção de sugestão via teclado (Enter)",
        )


class ContratoAutocompleteSelecaoTest(TestCase):
    """Dependência do fix #187: a seleção de sugestão do autocomplete popula
    o hidden por ATRIBUIÇÃO DIRETA (`hidden.value = cartorio.id`), sem
    disparar evento `input` — por isso o listener que limpa o hidden não
    apaga o ID recém-escolhido.

    Se um dia este contrato mudar (ex.: dispatchEvent(new Event('input'))
    após a seleção), o fix #187 quebra: o listener limparia o hidden recém-
    setado. Este teste registra a dependência."""

    JS_PATH = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'static', 'dominial', 'js', 'lancamento_form.js',
    )

    def setUp(self):
        with open(self.JS_PATH, encoding='utf-8') as f:
            self.js_src = f.read()

    def _funcao_selectCartorioSuggestion(self):
        match = re.search(
            r"function selectCartorioSuggestion\(index\) \{(.*?)\n    \}",
            self.js_src,
            re.DOTALL,
        )
        assert match is not None, (
            'Função selectCartorioSuggestion não encontrada em '
            'lancamento_form.js'
        )
        return match.group(1)

    def test_selecao_popula_o_hidden_com_o_id(self):
        """A seleção repõe o hidden — é o que torna seguro limpá-lo na
        digitação (ponto 2 da ATENÇÃO da issue: o POST lê name="
        cartorio_origem[]" e o fallback por nome no servidor só entra se o
        id vier vazio)."""
        corpo = self._funcao_selectCartorioSuggestion()
        self.assertIn(
            'hidden.value = cartorio.id',
            corpo,
            'selectCartorioSuggestion deve repovoar o hidden com o id do '
            'cartório selecionado (contrato do qual o fix #187 depende)',
        )

    def test_selecao_nao_dispara_evento_input(self):
        """Se a seleção passar a disparar `input` no campo, o listener do fix
        #187 limparia o hidden recém-setado e quebraria o fluxo de escolha."""
        corpo = self._funcao_selectCartorioSuggestion()
        self.assertNotIn(
            'dispatchEvent',
            corpo,
            'selectCartorioSuggestion não pode disparar eventos no campo: um '
            "dispatch de 'input' aqui faria o listener do fix #187 zerar o "
            'hidden recém-populado',
        )
