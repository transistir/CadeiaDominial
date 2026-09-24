"""Issue #187 — hidden `cartorio_origem_${index}` stale quando o operador
edita o nome do cartório (review Codex do PR #186).

Relato: em `configurarMAnterior` (static/dominial/js/origem_simples.js), o
campo de nome do cartório só registrava `keyup`/`blur` → `agendarMAnterior`.
Ao editar o nome SEM passar pelo autocomplete (ex.: escolheu 'Cartório X',
apagou e digitou 'Cartório Y'), a busca da M anterior disparava com o
`cartorio_id` antigo (X) enquanto o campo exibia 'Cartório Y' — o badge
renderizava informação do cartório errado, enganando a decisão de
'mesmo TI'/'outro TI'/'não consta'.

Fix: registrar também `input`, que limpa o hidden ANTES de chamar
`atualizarMAnterior` — imediata, sem o debounce de `agendarMAnterior`
(review Opus 5.5 PRE-MERGE). Com o hidden zerado, `atualizarMAnterior`
aborta o fetch em voo e esconde o badge NA HORA (guard do P2 #185, já
coberto por test_issue_167.GreptileP2RaceAbortTest); com o debounce, o
abort/ocultar só ocorreria 300ms depois — janela em que a resposta do
cartório antigo poderia renderizar durante a digitação seguinte.

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

# Contrato do teste restrito (test_selecao_nao_dispara_evento_input): proíbe a
# construção de um evento sintético de tipo 'input' — `new Event('input')`,
# `new InputEvent('input')` ou `new CustomEvent('input')` — no corpo da
# seleção. O prefixo é opcional via grupo `(?:Input|Custom)?`: o `?` precisa
# quantificar o GRUPO inteiro, não uma letra — a versão anterior
# (`new\s+Input?Event\(`) exigia o prefixo literal 'Inpu' e NÃO casava
# `new Event('input')`, exatamente o caso que o contrato devia bloquear
# (blocker convergente dos reviews Opus 5.5 + Codex r2). A sanidade do
# próprio regex é travada por SanidadeRegexContratoDisparoInputTest.
_RE_DISPARO_INPUT = re.compile(r"new\s+(?:Input|Custom)?Event\(\s*['\"`]input['\"`]")


class LimpaHiddenStaleAoEditarNomeTest(TestCase):
    """O bloco do cartorioNome em `configurarMAnterior` deve registrar
    `input` que limpa o hidden antes de chamar `atualizarMAnterior`
    (imediato); `blur` e `keyup` seguem com o debounce."""

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

    def test_listener_input_limpa_o_hidden_e_chama_atualizar_imediato(self):
        """BUG #187 (núcleo do fix) + review Opus 5.5 PRE-MERGE: dentro do
        listener `input`, o hidden `cartorio_origem_` é zerado ANTES da
        chamada a atualizarMAnterior — e a chamada é IMEDIATA, não o debounce
        de agendarMAnterior.

        A ordem importa: com o hidden já zerado, atualizarMAnterior cai no
        guard do P2 #185 (!cartorio_id), aborta o fetch em voo e esconde o
        badge NA HORA. Via agendarMAnterior, o abort/ocultar só ocorreria
        300ms depois — se a busca do cartório antigo resolvesse nesse
        intervalo (operador seleciona X e começa a digitar Y em seguida), o
        badge mostraria dados de X até a pausa: exatamente o estado
        enganoso, ainda que transitório, que a issue descreve."""
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
        self.assertNotIn(
            'agendarMAnterior(index)',
            corpo,
            "listener 'input' não pode usar o debounce (agendarMAnterior): "
            'o abort do fetch em voo e o ocultar do badge só ocorreriam '
            '300ms depois, deixando janela de badge stale',
        )
        pos_atualizar = corpo.find('atualizarMAnterior(index)')
        self.assertGreaterEqual(
            pos_atualizar,
            0,
            "listener 'input' deve chamar atualizarMAnterior(index) na hora "
            '(sem debounce) para abortar o fetch em voo imediatamente',
        )
        self.assertLess(
            pos_limpeza,
            pos_atualizar,
            'a limpeza do hidden deve vir ANTES da chamada a '
            'atualizarMAnterior',
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
        """Se a seleção passar a disparar `input` sintético no campo nome, o
        listener do fix #187 limparia o hidden recém-setado e quebraria o
        fluxo de escolha.

        Escopo restrito (review Opus 5.5 PRE-MERGE): o assert anterior
        bloqueava QUALQUER `dispatchEvent`, inclusive melhorias legítimas que
        não afetam o #187 (ex.: `hidden.dispatchEvent(new Event('change'))`).
        Agora proíbe apenas a construção de um evento de tipo 'input' —
        `new Event('input')`, `new InputEvent('input')` ou
        `new CustomEvent('input')` — que é o único dispatch capaz de zerar o
        hidden recém-populado. O regex (_RE_DISPARO_INPUT) é travado por
        SanidadeRegexContratoDisparoInputTest: a versão r1 (`Input?Event`)
        quantificava o `?` só sobre o `t` e NÃO casava `new Event('input')`
        (blocker r2, Opus 5.5 + Codex)."""
        corpo = self._funcao_selectCartorioSuggestion()
        self.assertIsNone(
            _RE_DISPARO_INPUT.search(corpo),
            'selectCartorioSuggestion não pode disparar evento `input` '
            "sintético no campo (new Event('input') / new "
            "InputEvent('input') / new CustomEvent('input')): o dispatch "
            'faria o listener do fix #187 zerar o hidden recém-populado '
            '(regex travado por SanidadeRegexContratoDisparoInputTest)',
        )


class SanidadeRegexContratoDisparoInputTest(TestCase):
    r"""Sanidade do PRÓPRIO regex do contrato (_RE_DISPARO_INPUT) — blocker
    dos reviews Opus 5.5 + Codex r2.

    O regex anterior (`new\s+Input?Event\(`) tinha o `?` quantificando só a
    letra `t`: casava `InputEvent` (e o inexistente `InpuEvent`), mas NÃO
    casava `new Event('input')` — e o Codex injetou
    `input.dispatchEvent(new Event('input'))` em memória e o teste do
    contrato continuou passando. Estes casos travam o regex contra as formas
    reais de disparo sintético."""

    def test_casa_disparos_sinteticos_de_input(self):
        """Toda forma de construir um evento sintético de tipo 'input' tem
        que casar — inclusive `new Event('input')`, que a versão anterior
        deixava passar."""
        casos = [
            "new Event('input')",
            'new Event("input", {bubbles: true})',
            "new InputEvent('input')",
            "new CustomEvent('input')",
            "input.dispatchEvent(new Event('input'))",
            "input.dispatchEvent(new CustomEvent(`input`))",
        ]
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertIsNotNone(
                    _RE_DISPARO_INPUT.search(caso),
                    f'o regex do contrato deve casar: {caso}',
                )

    def test_nao_casa_outros_tipos_de_evento(self):
        """Eventos de outro tipo (change/blur/keyup) NÃO casam — o contrato
        é restrito ao tipo 'input', o único capaz de zerar o hidden recém-
        populado."""
        casos = [
            "new Event('change')",
            'new Event("change", {bubbles: true})',
            "new InputEvent('change')",
            "new CustomEvent('blur')",
            "new Event('keyup')",
        ]
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertIsNone(
                    _RE_DISPARO_INPUT.search(caso),
                    f'o regex do contrato NÃO deve casar outro tipo de '
                    f'evento: {caso}',
                )
