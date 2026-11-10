"""Testes do parser de rótulos de lançamento (I-11b / #322).

As regras vêm da decisão do cliente (Hiure, 09/11): lançamento SEMPRE
começa com ``R`` (registro) ou ``Av`` (averbação); ``M`` é número de
matrícula — rótulo válido, mas nunca um lançamento; ``"R: 1-237"`` traz
número de ato ``1`` e matrícula ``237``, e o texto depois do carimbo é
ignorado. ``classificar_atos`` consome o payload da extração
(``document`` + ``acts``) e devolve o cabeçalho do início de matrícula,
os lançamentos em ordem REVERSA e os rótulos não reconhecidos.
"""

from django.test import TestCase

from ia_ocr.rotulos import (
    Classificacao, analisar_rotulo, classificar_atos, compor_numero_lancamento,
)


def _campo(normalized=None, raw=None):
    """Campo de valor A3 no formato mínimo que o parser lê."""
    return {'raw': raw, 'normalized': normalized}


def _ato(ordem, rotulo, tipo_sugerido=None, **extras):
    """Ato A3 mínimo: rótulo + tipo_sugerido + data.

    Sem tipo explícito, o sugerido acompanha o prefixo do rótulo (a roda
    que o serviço real acerta no dia a dia).
    """
    if tipo_sugerido is None:
        tipo_sugerido = 'averbacao' if rotulo[:2].lower() == 'av' else 'registro'
    ato = {
        'ordem': ordem,
        'rotulo': _campo(rotulo, rotulo),
        'tipo_sugerido': _campo(tipo_sugerido, rotulo),
        'data': _campo('2020-02-15', '15 de fevereiro de 2020'),
        'partes': [],
    }
    ato.update(extras)
    return ato


# Payload real: campos críticos do cabeçalho chegam com ``normalized=None``
# e o texto de OCR no ``raw`` (extração id 10, umbelino-extracao-v1.1).
DOCUMENTO_REAL = {
    'tipo': _campo('matricula', 'Matrícula'),
    'numero': _campo(None, '42.718'),
    'livro': _campo('2-RG', 'Livro 2-RG'),
    'cartorio': _campo(None, 'CRI de Itamaraju'),
    'area': _campo(None, '12,5 ha'),
    'data': _campo(None, '06 de maio de 2002'),
    'imovel_descricao': _campo(None, 'O imóvel rural denominado Sítio Boa Vista'),
}


class AnalisarRotuloTest(TestCase):
    """Cada regra do rótulo, uma asserção por campo do resultado."""

    def test_registros(self):
        casos = [
            ('R-1', '1', None),
            ('R: 1-237', '1', '237'),
            ('R 1', '1', None),
            ('R:1-237', '1', '237'),
            ('r-1', '1', None),
            (
                'R: 5-237 – PROTOCOLO Nº 13.607 – Itamaraju, '
                '06 de maio de 2002. O ato continua aqui.',
                '5', '237',
            ),
            ('R-1/42.718', '1', '42.718'),
            ('R-007', '007', None),  # zeros à esquerda preservados
            ('R:  1   -   237', '1', '237'),  # espaços internos colapsados
        ]
        for texto, numero, matricula in casos:
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertTrue(analisado.reconhecido)
                self.assertIsNone(analisado.motivo)
                self.assertEqual(analisado.tipo, 'registro')
                self.assertEqual(analisado.numero, numero)
                self.assertEqual(analisado.matricula, matricula)
                self.assertFalse(analisado.eh_matricula)

    def test_averbacoes(self):
        casos = [
            ('Av-6', '6', None),
            ('Av-2', '2', None),
            ('Av. 3', '3', None),
            ('AV: 2', '2', None),
            ('av-6', '6', None),
            (
                'Av: 6-237 – PROTOCOLO nº 25.825 – Itamaraju, '
                '06 de maio de 2002.',
                '6', '237',
            ),
        ]
        for texto, numero, matricula in casos:
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertTrue(analisado.reconhecido)
                self.assertIsNone(analisado.motivo)
                self.assertEqual(analisado.tipo, 'averbacao')
                self.assertEqual(analisado.numero, numero)
                self.assertEqual(analisado.matricula, matricula)
                self.assertFalse(analisado.eh_matricula)

    def test_separadores_tipograficos_valem_como_hifen(self):
        # P2-4 (#322 rodada 4): o OCR/Word traz meia-risca (U+2013) e
        # travessão (U+2014) no lugar do hífen — 'R–5' é registro nº 5, não
        # 'sem_prefixo'; entre os números, 'R: 1—237' traz a matrícula 237.
        casos = [
            ('R–5', 'registro', '5', None),
            ('R—5', 'registro', '5', None),
            ('R: 1–237', 'registro', '1', '237'),
            ('R: 1—237', 'registro', '1', '237'),
            ('Av–6', 'averbacao', '6', None),
            ('M–3–14511', None, None, '14511'),
        ]
        for texto, tipo, numero, matricula in casos:
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertTrue(analisado.reconhecido)
                self.assertEqual(analisado.tipo, tipo)
                self.assertEqual(analisado.numero, numero)
                self.assertEqual(analisado.matricula, matricula)
                self.assertEqual(analisado.eh_matricula, texto[:1] in 'Mm')

    def test_matriculas_sao_rotulos_validos_que_nao_sao_lancamento(self):
        casos = [
            ('M-3-14511', '14511'),
            ('M: 12.345', '12.345'),  # pontuação preservada como veio
            ('m-14511', '14511'),
        ]
        for texto, matricula in casos:
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertTrue(analisado.reconhecido)
                self.assertIsNone(analisado.motivo)
                self.assertTrue(analisado.eh_matricula)
                self.assertIsNone(analisado.tipo)
                self.assertIsNone(analisado.numero)
                self.assertEqual(analisado.matricula, matricula)

    def test_prefixo_sem_numero_nao_e_lancamento(self):
        # P2-5 (#322 rodada 3): prefixo R/Av/M SEM número não é lançamento —
        # 'Av. Brasil, 123' é endereço, 'R$ 5.000' é valor, 'R'/'R:'/'Av -'
        # são carimbo vazio. Novo motivo; o destino é o bucket de não
        # reconhecidos (UI, #321).
        for texto in ('Av. Brasil, 123', 'R$ 5.000', 'R', 'R:', 'Av -', 'M'):
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertFalse(analisado.reconhecido)
                self.assertEqual(analisado.motivo, 'sem_numero')
                self.assertIsNone(analisado.numero)
                self.assertIsNone(analisado.tipo)
                self.assertFalse(analisado.eh_matricula)

    def test_vazios(self):
        for texto in ('', None, '   '):
            with self.subTest(texto=repr(texto)):
                analisado = analisar_rotulo(texto)
                self.assertFalse(analisado.reconhecido)
                self.assertEqual(analisado.motivo, 'vazio')
                self.assertIsNone(analisado.tipo)
                self.assertIsNone(analisado.numero)

    def test_texto_de_cabecalho_nao_tem_prefixo(self):
        analisado = analisar_rotulo(
            'O imóvel rural denominado Sítio Boa Vista, com 12,5 ha.',
        )
        self.assertFalse(analisado.reconhecido)
        self.assertEqual(analisado.motivo, 'sem_prefixo')

    def test_prefixo_desconhecido(self):
        for texto in ('X-1', 'X 42.718'):
            with self.subTest(texto=texto):
                analisado = analisar_rotulo(texto)
                self.assertFalse(analisado.reconhecido)
                self.assertEqual(analisado.motivo, 'prefixo_desconhecido')

    def test_entrada_estranha_nunca_levanta_excecao(self):
        estranhos = ({}, ['R-1'], 42, 3.14, object(), {'R-1': 2})
        for texto in estranhos:
            with self.subTest(texto=repr(texto)):
                analisado = analisar_rotulo(texto)
                self.assertFalse(analisado.reconhecido)
                self.assertIsNotNone(analisado.motivo)


class ClassificarAposTest(TestCase):
    """classificar_atos sobre o payload da extração."""

    def test_payload_real_com_sete_atos(self):
        payload = {
            'document': dict(DOCUMENTO_REAL),
            'acts': [
                _ato(1, 'R-1'), _ato(2, 'Av-2'), _ato(3, 'Av-3'),
                _ato(4, 'R-4'), _ato(5, 'R-5'), _ato(6, 'Av-6'),
                _ato(7, 'Av-7'),
            ],
            'closure': None,
        }

        classificacao = classificar_atos(payload)

        self.assertIsInstance(classificacao, Classificacao)
        self.assertEqual(classificacao.inicio_matricula, {
            'livro': '2-RG',
            'numero': '42.718',
            'cartorio': 'CRI de Itamaraju',
            'area': '12,5 ha',
            'data': '06 de maio de 2002',
            'imovel_descricao': 'O imóvel rural denominado Sítio Boa Vista',
        })
        self.assertEqual(
            [item['ordem'] for item in classificacao.lancamentos],
            [7, 6, 5, 4, 3, 2, 1],  # ordem REVERSA
        )
        self.assertEqual(
            {item['ordem']: item['tipo'] for item in classificacao.lancamentos},
            {
                1: 'registro', 2: 'averbacao', 3: 'averbacao',
                4: 'registro', 5: 'registro', 6: 'averbacao', 7: 'averbacao',
            },
        )
        self.assertEqual(
            {item['ordem']: item['numero'] for item in classificacao.lancamentos},
            {ordem: str(ordem) for ordem in range(1, 8)},
        )
        self.assertTrue(all(
            item['matricula'] is None for item in classificacao.lancamentos
        ))
        self.assertTrue(all(
            item['divergencia'] is False for item in classificacao.lancamentos
        ))
        self.assertEqual(classificacao.nao_reconhecidos, [])
        # 'ato' é o dict ORIGINAL do payload (a tela consome o resto dele).
        self.assertIs(classificacao.lancamentos[0]['ato'], payload['acts'][6])

    def test_ordem_como_string_sai_em_ordem_reversa(self):
        # Payload real: 'ordem' chega como STRING ('1', '7'); a chave de
        # ordenação converte para inteiro — sem a conversão tudo empata em
        # 0 e a lista sai na ordem original, não na reversa (#322).
        payload = {'acts': [
            _ato('1', 'R-1'), _ato('2', 'Av-2'), _ato('7', 'Av-7'),
        ]}

        classificacao = classificar_atos(payload)

        self.assertEqual(
            [item['ordem'] for item in classificacao.lancamentos],
            ['7', '2', '1'],
        )

    def test_ordem_ausente_ou_sem_digito_cai_no_indice(self):
        # P1-2 (#322 rodada 3): sem ordem (None) ou com texto sem dígito
        # ('topo'), a chave é o ÍNDICE do payload + 1 — o item do meio do
        # documento fica no MEIO, não vai parar no fim; o campo 'ordem'
        # exposto segue como veio, sem conversão.
        payload = {'acts': [
            _ato(None, 'R-1'), _ato('topo', 'R-2'), _ato(3, 'R-3'),
        ]}

        classificacao = classificar_atos(payload)

        self.assertEqual(
            [item['ordem'] for item in classificacao.lancamentos],
            [3, 'topo', None],
        )
        self.assertEqual(
            [item['numero'] for item in classificacao.lancamentos],
            ['3', '2', '1'],
        )

    def test_sem_ordem_a_lista_sai_reversa_pelo_indice(self):
        # P1-2: nenhum ato com 'ordem' — a chave é o índice do payload + 1 e
        # a lista sai em ordem REVERSA ([R-1, Av-2, R-3] → [R-3, Av-2,
        # R-1]); o campo exposto traz o índice + 1 no lugar do ausente.
        atos = [_ato(1, 'R-1'), _ato(2, 'Av-2'), _ato(3, 'R-3')]
        for ato in atos:
            del ato['ordem']

        classificacao = classificar_atos({'acts': atos})

        self.assertEqual(
            [item['numero'] for item in classificacao.lancamentos],
            ['3', '2', '1'],
        )
        self.assertEqual(
            [item['tipo'] for item in classificacao.lancamentos],
            ['registro', 'averbacao', 'registro'],
        )
        self.assertEqual(
            [item['ordem'] for item in classificacao.lancamentos],
            [3, 2, 1],
        )

    def test_ordem_none_no_meio_fica_no_meio(self):
        # P1-2, cenário misto do review: ordens ['1', None, '3'] — o None
        # ordena pelo índice + 1 (2) e fica ENTRE o 3 e o 1; exposto como
        # veio (None presente não é ausente).
        payload = {'acts': [
            _ato('1', 'R-1'), _ato(None, 'Av-2'), _ato('3', 'R-3'),
        ]}

        classificacao = classificar_atos(payload)

        self.assertEqual(
            [item['ordem'] for item in classificacao.lancamentos],
            ['3', None, '1'],
        )
        self.assertEqual(
            [item['numero'] for item in classificacao.lancamentos],
            ['3', '2', '1'],
        )

    def test_ordem_nan_ou_infinito_nao_levanta_excecao(self):
        # P2-6: o json.loads aceita NaN/Infinity como float — int() levantaria
        # ValueError/OverflowError; a chave cai no índice do payload + 1.
        for ordem in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(ordem=ordem):
                classificacao = classificar_atos({'acts': [
                    _ato(ordem, 'R-1'), _ato(2, 'Av-2'),
                ]})

                self.assertEqual(
                    [item['numero'] for item in classificacao.lancamentos],
                    ['2', '1'],
                )
                self.assertEqual(
                    [item['ordem'] for item in classificacao.lancamentos],
                    [2, ordem],
                )

    def test_acts_nao_lista_devolve_listas_vazias(self):
        # P2-6: 'acts' que não é lista (número, bool, texto, dict) não é
        # iterável de atos — listas vazias, nunca TypeError.
        for acts in (5, True, 'não é lista', {'ordem': 1}, None):
            with self.subTest(acts=repr(acts)):
                classificacao = classificar_atos({'acts': acts})

                self.assertEqual(classificacao.lancamentos, [])
                self.assertEqual(classificacao.nao_reconhecidos, [])

    def test_tipo_sugerido_divergente_prevalece_o_do_rotulo(self):
        payload = {'acts': [_ato(4, 'R-4', 'averbacao')]}

        (item,) = classificar_atos(payload).lancamentos

        self.assertEqual(item['tipo'], 'registro')
        self.assertTrue(item['divergencia'])

    def test_tipo_sugerido_vazio_usa_o_prefixo_do_rotulo(self):
        payload = {'acts': [_ato(4, 'R-4', None)]}

        (item,) = classificar_atos(payload).lancamentos

        self.assertEqual(item['tipo'], 'registro')
        self.assertFalse(item['divergencia'])

    def test_tipo_sugerido_invalido_usa_o_prefixo_do_rotulo(self):
        payload = {'acts': [_ato(9, 'Av-9', 'transcricao')]}

        (item,) = classificar_atos(payload).lancamentos

        self.assertEqual(item['tipo'], 'averbacao')
        self.assertFalse(item['divergencia'])

    def test_rotulo_sem_prefixo_vai_para_nao_reconhecidos(self):
        texto = 'O imóvel rural denominado Sítio Boa Vista'
        payload = {'acts': [_ato(2, texto)]}

        classificacao = classificar_atos(payload)

        self.assertEqual(classificacao.lancamentos, [])
        (item,) = classificacao.nao_reconhecidos
        self.assertEqual(item['ordem'], 2)
        self.assertEqual(item['rotulo'], texto)
        self.assertEqual(item['motivo'], 'sem_prefixo')
        self.assertIs(item['ato'], payload['acts'][0])

    def test_rotulo_com_prefixo_sem_numero_vai_para_nao_reconhecidos(self):
        # P2-5: 'Av. Brasil, 123' tem prefixo conhecido mas SEM número do
        # ato — não entra em lancamentos; vai ao bucket com 'sem_numero'.
        payload = {'acts': [_ato(4, 'Av. Brasil, 123')]}

        classificacao = classificar_atos(payload)

        self.assertEqual(classificacao.lancamentos, [])
        (item,) = classificacao.nao_reconhecidos
        self.assertEqual(item['motivo'], 'sem_numero')

    def test_rotulo_de_matricula_nao_e_lancamento_nem_erro(self):
        payload = {'acts': [_ato(1, 'M-3-14511', None)]}

        classificacao = classificar_atos(payload)

        self.assertEqual(classificacao.lancamentos, [])
        self.assertEqual(classificacao.nao_reconhecidos, [])

    def test_r2_com_matricula_no_rotulo(self):
        payload = {'acts': [_ato(2, 'Av: 2-237 – PROTOCOLO nº 25.825', 'averbacao')]}

        (item,) = classificar_atos(payload).lancamentos

        self.assertEqual(item['tipo'], 'averbacao')
        self.assertEqual(item['numero'], '2')
        self.assertEqual(item['matricula'], '237')

    def test_document_ausente_ou_vazio_nao_tem_inicio_matricula(self):
        self.assertIsNone(classificar_atos({'acts': []}).inicio_matricula)
        self.assertIsNone(
            classificar_atos({'document': {}, 'acts': []}).inicio_matricula
        )

    def test_payload_vazio_ou_estranho_nao_levanta_excecao(self):
        for payload in ({}, None, [], 'não é payload'):
            with self.subTest(payload=repr(payload)):
                classificacao = classificar_atos(payload)
                self.assertIsNone(classificacao.inicio_matricula)
                self.assertEqual(classificacao.lancamentos, [])
                self.assertEqual(classificacao.nao_reconhecidos, [])

    def test_payload_sem_acts_tem_so_o_cabecalho(self):
        classificacao = classificar_atos({'document': dict(DOCUMENTO_REAL)})

        self.assertIsNotNone(classificacao.inicio_matricula)
        self.assertEqual(classificacao.lancamentos, [])
        self.assertEqual(classificacao.nao_reconhecidos, [])

    def test_ato_estranho_nao_levanta_excecao(self):
        # Ato que não é dict é ignorado; dict sem rótulo cai em 'vazio'.
        payload = {'acts': ['não é ato', None, {'sem': 'nada'}]}

        classificacao = classificar_atos(payload)

        self.assertEqual(classificacao.lancamentos, [])
        self.assertEqual(len(classificacao.nao_reconhecidos), 1)
        self.assertEqual(classificacao.nao_reconhecidos[0]['motivo'], 'vazio')


class ComporNumeroLancamentoTest(TestCase):
    """compor_numero_lancamento: o formato canônico do V1 (#322 rodada 3).

    Decisão de produto (orquestrador, por falta de resposta do cliente): a
    importação grava o MESMO texto do fluxo manual
    (``lancamento_form_service._gerar_numero_lancamento``) — os sete
    consumidores ordenam por ``^(R|AV)\\d+``.
    """

    def test_registro_e_averbacao_com_sigla(self):
        self.assertEqual(
            compor_numero_lancamento('registro', '5', 'M237'), 'R5 M237',
        )
        self.assertEqual(
            compor_numero_lancamento('averbacao', '6', 'M237'), 'AV6 M237',
        )

    def test_sigla_vazia_compoe_sem_ela(self):
        self.assertEqual(compor_numero_lancamento('registro', '5', ''), 'R5')
        self.assertEqual(
            compor_numero_lancamento('averbacao', '6', None), 'AV6',
        )

    def test_inicio_de_matricula_e_so_a_sigla(self):
        self.assertEqual(
            compor_numero_lancamento('inicio_matricula', '5', 'M237'),
            'M237',
        )
        self.assertIsNone(
            compor_numero_lancamento('inicio_matricula', '5', ''),
        )

    def test_sem_numero_do_ato_nao_compoe_prefixo(self):
        # P2-5 na gravação: sem número do ato não há o que prefixar.
        self.assertIsNone(compor_numero_lancamento('registro', None, 'M237'))
        self.assertIsNone(compor_numero_lancamento('averbacao', '', 'M237'))

    def test_tipo_fora_dos_tres_devolve_o_numero(self):
        # Mesmo fallback do fluxo manual: número como veio.
        self.assertEqual(
            compor_numero_lancamento('transcricao', '5', 'M237'), '5',
        )
        self.assertIsNone(compor_numero_lancamento(None, None, 'M237'))
