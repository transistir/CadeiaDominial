"""Vocabulário pinado (#372): cópia vendorizada e casamento sem produção.

O app consome uma cópia byte a byte do artefato sintético do ocr-service
(#74). Estes testes provam três coisas: a cópia confere com os hashes
pinados, o casamento segue exato → normalizado → fuzzy sem inventar valor,
e carregar/casar não abrem rede nem leem nada fora do pacote.
"""

import ast
import io
import socket
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from ia_ocr import vocabulario

PERMITIDOS = frozenset({
    'dataclasses', 'difflib', 'functools', 'hashlib', 'json', 'pathlib',
    're', 'typing', 'unicodedata',
})


class ArtefatoPinadoTest(SimpleTestCase):
    def setUp(self):
        vocabulario.carregar.cache_clear()
        vocabulario.entradas.cache_clear()
        self.addCleanup(vocabulario.carregar.cache_clear)
        self.addCleanup(vocabulario.entradas.cache_clear)

    def test_copia_byte_a_byte_confere_com_o_sha256_pinado(self):
        self.assertEqual(
            vocabulario.sha256_do_arquivo(), vocabulario.SHA256_DO_ARQUIVO,
        )

    def test_arquivo_vendorizado_mora_no_pacote(self):
        raiz = Path(vocabulario.__file__).resolve().parent
        self.assertEqual(
            vocabulario.CAMINHO_VOCABULARIO.resolve(),
            raiz / 'schemas' / 'vocabulario_prod.json',
        )

    def test_hash_canonico_bate_com_o_meta_sha256_do_artefato(self):
        documento = vocabulario.carregar()

        self.assertEqual(documento['schema'], vocabulario.SCHEMA)
        self.assertEqual(
            documento['meta']['sha256'], vocabulario.SHA256_DO_DOCUMENTO,
        )
        self.assertEqual(
            vocabulario.sha256_do_documento(documento),
            vocabulario.SHA256_DO_DOCUMENTO,
        )

    def test_carregar_falha_se_os_bytes_divergirem(self):
        with mock.patch.object(vocabulario, 'SHA256_DO_ARQUIVO', '0' * 64):
            with self.assertRaises(vocabulario.VocabularioInvalido):
                vocabulario.carregar()

    def test_carregar_falha_se_o_documento_divergir(self):
        with mock.patch.object(vocabulario, 'SHA256_DO_DOCUMENTO', '0' * 64):
            with self.assertRaises(vocabulario.VocabularioInvalido):
                vocabulario.carregar()

    def test_arquivo_ausente_vira_vocabulario_invalido(self):
        with mock.patch.object(
            vocabulario, 'CAMINHO_VOCABULARIO', Path('/nao/existe/vocabulario.json'),
        ):
            with self.assertRaises(vocabulario.VocabularioInvalido):
                vocabulario.carregar()

    def test_json_invalido_vira_vocabulario_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruim = Path(tmp) / 'vocabulario_prod.json'
            ruim.write_text('{', encoding='utf-8')
            with mock.patch.object(vocabulario, 'CAMINHO_VOCABULARIO', ruim), \
                    mock.patch.object(
                        vocabulario, 'sha256_do_arquivo',
                        return_value=vocabulario.SHA256_DO_ARQUIVO,
                    ):
                with self.assertRaises(vocabulario.VocabularioInvalido):
                    vocabulario.carregar()

    def test_entradas_do_campo_forma(self):
        valores = {entrada.valor for entrada in vocabulario.entradas('forma')}

        self.assertIn('Compra e Venda', valores)
        self.assertIn('Doação', valores)
        self.assertGreaterEqual(len(valores), 6)


class SemAcessoAProducaoTest(SimpleTestCase):
    def setUp(self):
        vocabulario.carregar.cache_clear()
        vocabulario.entradas.cache_clear()
        self.addCleanup(vocabulario.carregar.cache_clear)
        self.addCleanup(vocabulario.entradas.cache_clear)

    def _imports(self):
        arvore = ast.parse(Path(vocabulario.__file__).read_text('utf-8'))
        raizes = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                raizes.update(alias.name.split('.')[0] for alias in no.names)
            elif isinstance(no, ast.ImportFrom) and no.level == 0:
                raizes.add((no.module or '').split('.')[0])
        return raizes

    def test_modulo_importa_so_stdlib_de_leitura_local(self):
        # Rede (requests/urllib/socket/http) e banco (django/psycopg) entram
        # aqui como falha: o vocabulário é lido do disco, nada mais.
        self.assertLessEqual(self._imports(), PERMITIDOS)

    def test_carregar_e_casar_nao_abrem_rede(self):
        with mock.patch.object(
            socket, 'socket', side_effect=AssertionError('rede proibida'),
        ), mock.patch.object(
            socket, 'create_connection',
            side_effect=AssertionError('rede proibida'),
        ):
            casamento = vocabulario.casar('forma', 'Venda e compra')

        self.assertEqual(casamento.valor, 'Compra e Venda')

    def test_le_apenas_o_json_vendorizado(self):
        real = io.open
        abertos = []

        def espiao(arquivo, *args, **kwargs):
            abertos.append(Path(arquivo).resolve())
            return real(arquivo, *args, **kwargs)

        with mock.patch('io.open', side_effect=espiao):
            vocabulario.carregar()

        self.assertEqual(
            set(abertos), {vocabulario.CAMINHO_VOCABULARIO.resolve()},
        )


class CasamentoTest(SimpleTestCase):
    def setUp(self):
        vocabulario.carregar.cache_clear()
        vocabulario.entradas.cache_clear()
        self.addCleanup(vocabulario.carregar.cache_clear)
        self.addCleanup(vocabulario.entradas.cache_clear)

    def test_exato_mantem_o_valor_canonico(self):
        casamento = vocabulario.casar('forma', 'Compra e Venda')

        self.assertEqual(casamento.metodo, vocabulario.EXATO)
        self.assertEqual(casamento.valor, 'Compra e Venda')

    def test_normalizado_ignora_caixa_e_acento(self):
        casamento = vocabulario.casar('forma', 'cessao de direitos')

        self.assertEqual(casamento.metodo, vocabulario.NORMALIZADO)
        self.assertEqual(casamento.valor, 'Cessão de Direitos')

    def test_normalizado_ignora_a_ordem_dos_tokens(self):
        casamento = vocabulario.casar('forma', 'Venda e compra')

        self.assertEqual(casamento.metodo, vocabulario.NORMALIZADO)
        self.assertEqual(casamento.valor, 'Compra e Venda')

    def test_fuzzy_casa_erro_de_digitacao_com_vencedor_unico(self):
        casamento = vocabulario.casar('forma', 'Comrpa e Venda')

        self.assertEqual(casamento.metodo, vocabulario.FUZZY)
        self.assertEqual(casamento.valor, 'Compra e Venda')
        self.assertGreaterEqual(casamento.similaridade, vocabulario.LIMIAR_FUZZY)

    def test_sem_candidato_suficiente_nao_devolve_valor(self):
        casamento = vocabulario.casar('forma', 'Permuta')

        self.assertFalse(casamento.casa)
        self.assertIsNone(casamento.valor)
        self.assertEqual(casamento.motivo, vocabulario.MOTIVO_BAIXA_CONFIANCA)

    def test_dacao_nao_casa_com_doacao(self):
        # 'Daçao' (pagamento em dinheiro) não é erro de digitação de
        # 'Doação': a similaridade global sozinha daria falso positivo.
        casamento = vocabulario.casar('forma', 'Daçao')

        self.assertFalse(casamento.casa)
        self.assertIsNone(casamento.valor)
        self.assertEqual(casamento.motivo, vocabulario.MOTIVO_BAIXA_CONFIANCA)

    def test_valor_canonico_duplicado_nao_quebra(self):
        # Dois ``Entrada`` com o MESMO valor empatam em ratio e valor; a
        # ordenação não pode comparar ``Entrada`` (TypeError) — o empate
        # continua sendo empate.
        entradas = (
            vocabulario.Entrada('Compra e Venda', 6),
            vocabulario.Entrada('Compra e Venda', 2),
            vocabulario.Entrada('Venda e Compra', 1),
        )
        with mock.patch.object(vocabulario, 'entradas', return_value=entradas):
            casamento = vocabulario.casar('forma', 'Comrpa e Venda')

        self.assertFalse(casamento.casa)
        self.assertEqual(casamento.motivo, vocabulario.MOTIVO_EMPATE)

    def test_valor_vazio_nao_casa(self):
        casamento = vocabulario.casar('forma', '   ')

        self.assertFalse(casamento.casa)
        self.assertEqual(casamento.motivo, vocabulario.MOTIVO_VAZIO)

    def test_empate_entre_candidatos_mantem_o_valor_original(self):
        entradas = (
            vocabulario.Entrada('Compra e Venda', 6),
            vocabulario.Entrada('Venda e Compra', 1),
        )
        with mock.patch.object(vocabulario, 'entradas', return_value=entradas):
            casamento = vocabulario.casar('forma', 'venda e compra')

        self.assertFalse(casamento.casa)
        self.assertEqual(casamento.motivo, vocabulario.MOTIVO_EMPATE)
