"""Mapa único de classe das pendências: bloqueante × informativo (#332)."""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from ia_ocr.classe_pendencia import (
    BLOQUEANTE,
    CLASSE_DO_MOTIVO,
    INFORMATIVO,
    eh_bloqueante,
)
from ia_ocr.formulario.areas import (
    MOTIVO_AREA_EM_OUTRA_UNIDADE, _area_em_outra_unidade,
)
from ia_ocr.formulario.forma_transacao import (
    MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO, _data_transacao_do_instrumento,
)
from ia_ocr.formulario.origens import (
    MOTIVO_LIDO_SEM_CAMPO, _lidos_sem_campo,
)

MAPA_ESPERADO = {
    # Bloqueantes do ato
    'unidade_area': BLOQUEANTE,
    'inicio_sem_origem': BLOQUEANTE,
    'inicio_sem_data': BLOQUEANTE,
    'cartorio_transmissao_nao_cadastrado': BLOQUEANTE,
    'cartorio_origem_nao_cadastrado': BLOQUEANTE,
    # Bloqueantes do motor legado
    'nenhum_ato': BLOQUEANTE,
    'revisao_pendente': BLOQUEANTE,
    'escolha_pendente': BLOQUEANTE,
    'decisao_perdida': BLOQUEANTE,
    'criar_novo_sem_nome': BLOQUEANTE,
    'match_invalidado': BLOQUEANTE,
    'obrigatorio_ausente': BLOQUEANTE,
    'valor_incompativel_destino': BLOQUEANTE,
    'valor_acima_do_limite_destino': BLOQUEANTE,
    # Informativos do ato
    'lido_sem_campo': INFORMATIVO,
    'forma_ajustada_vocabulario': INFORMATIVO,
    'forma_titulo_reinterpretados': INFORMATIVO,
    'data_transacao_do_instrumento': INFORMATIVO,
    'area_descartada': INFORMATIVO,
    # Informativos de avisos()
    'livro_origem_nao_consta': INFORMATIVO,
    'folha_origem_nao_consta': INFORMATIVO,
    'origem_homonimo_outro_tipo': INFORMATIVO,
    'requer_forma': INFORMATIVO,
    'requer_observacao': INFORMATIVO,
    'requer_livro_origem': INFORMATIVO,
    'requer_folha_origem': INFORMATIVO,
    'requer_data_origem': INFORMATIVO,
    'requer_transmissao': INFORMATIVO,
}


class MapaDeClasseTest(SimpleTestCase):
    def test_classe_de_cada_motivo(self):
        for motivo, classe in MAPA_ESPERADO.items():
            with self.subTest(motivo=motivo):
                self.assertEqual(CLASSE_DO_MOTIVO[motivo], classe)
                self.assertIs(eh_bloqueante(motivo), classe is BLOQUEANTE)

    def test_motivo_desconhecido_e_bloqueante(self):
        self.assertIs(eh_bloqueante('motivo_que_ninguem_conhece'), True)

    def test_todo_motivo_do_formulario_tem_classe(self):
        motivos = {
            MOTIVO_AREA_EM_OUTRA_UNIDADE,
            MOTIVO_LIDO_SEM_CAMPO,
            MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO,
            'forma_ajustada_vocabulario',
            'forma_titulo_reinterpretados',
        }
        self.assertEqual(motivos - set(CLASSE_DO_MOTIVO), set())


class ProdutoresLeemOMapaTest(SimpleTestCase):
    def test_origem_lido_sem_campo_le_o_mapa(self):
        ato = SimpleNamespace(origem={'data': '2020-01-01'}, partes=[])
        extracao = SimpleNamespace(payload_servico=None, payload={})

        (padrao,) = _lidos_sem_campo(extracao, 0, ato)
        self.assertFalse(padrao['bloqueante'])

        with mock.patch.dict(
            CLASSE_DO_MOTIVO, {MOTIVO_LIDO_SEM_CAMPO: BLOQUEANTE},
        ):
            (virado,) = _lidos_sem_campo(extracao, 0, ato)
        self.assertTrue(virado['bloqueante'])

    def test_area_le_o_mapa(self):
        campo = SimpleNamespace(
            status_revisao='sugerido', area_convertida=False,
            motivos_revisao=(MOTIVO_AREA_EM_OUTRA_UNIDADE,),
            normalized='12.50', raw='12,50 alqueires',
        )
        extracao = SimpleNamespace(
            payload_servico={'acts': [{'area': {'unidade': 'alqueires'}}]},
            payload=None,
        )
        linhas = {'/acts/0/area': campo}

        padrao = _area_em_outra_unidade(extracao, 0, linhas, '/acts/0')
        self.assertTrue(padrao['bloqueante'])

        with mock.patch.dict(
            CLASSE_DO_MOTIVO, {MOTIVO_AREA_EM_OUTRA_UNIDADE: INFORMATIVO},
        ):
            virado = _area_em_outra_unidade(extracao, 0, linhas, '/acts/0')
        self.assertFalse(virado['bloqueante'])

    def test_data_transacao_le_o_mapa(self):
        _data, padrao, _derivou = _data_transacao_do_instrumento(
            'Escritura pública de 15/02/2020', None,
        )
        self.assertIsNotNone(padrao)
        self.assertFalse(padrao['bloqueante'])

        with mock.patch.dict(
            CLASSE_DO_MOTIVO, {MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO: BLOQUEANTE},
        ):
            _data, virado, _derivou = _data_transacao_do_instrumento(
                'Escritura pública de 15/02/2020', None,
            )
        self.assertTrue(virado['bloqueante'])
