"""Seletor de cartório nunca vazio (#315): fallback pela comarca do texto."""

import json

from dominial.models import Cartorios
from ia_ocr import revisao
from ia_ocr.models import CampoSugerido
from ia_ocr.revisao import IndiceCartorios

from . import test_revisao_tela as tela
from .test_revisao_tela import _atributos, _descendentes, _elementos

CHAVE = '/document/cartorio'
CABECALHO = (
    '1º OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS\n'
    'COMARCA DE ITAMARAJU - ESTADO DA BAHIA\nMatrícula 1\n'
)


class CartorioFallbackTest(tela.TelaRevisaoBase):
    def setUp(self):
        super().setUp()
        self.itamaraju = Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju', cidade='ITAMARAJU',
            estado='BA', cns='140160',
        )
        self.outro = Cartorios.objects.create(
            nome='Registro de Imóveis de Prado', cidade='PRADO',
            estado='BA', cns='140161',
        )

    def _com_cartorio_sem_candidatos(self, texto=CABECALHO):
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=texto)
        extracao = self._extracao()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            raw=None, normalized=None, match_candidatos=[],
            cartorio_escolhido=None, criar_novo=False,
        )
        return extracao

    def test_comarca_do_cabecalho_inclui_cartorio_da_cidade(self):
        extracao = self._com_cartorio_sem_candidatos()
        ids = self._candidatos(extracao)
        self.assertEqual(ids, [self.itamaraju.pk])

    def _candidatos(self, extracao):
        return revisao.candidatos_cartorio_fallback(
            extracao, CHAVE, IndiceCartorios(),
            revisao.comarca_do_documento(extracao),
        )

    def _lista_completa(self):
        """Lista completa do índice: todos os cartórios por (nome, id).

        Inclui o cartório da fixture base (``CRI Teste …``, SP), cujo nome
        precede ``Registro de Imóveis …`` na ordenação.
        """
        return [
            self.documento.cartorio_id, self.itamaraju.pk, self.outro.pk,
        ]

    def test_comarca_citada_no_corpo_nao_conta(self):
        corpo = (
            'MATRÍCULA Nº 1 - LIVRO 2 - REGISTRO GERAL\n' + 'x ' * 400
            + '\ntranscrição oriunda da COMARCA DE PRADO, conforme registro'
        )
        extracao = self._com_cartorio_sem_candidatos(corpo)
        # A citação no corpo não vira comarca; sem cabeçalho, o seletor cai
        # na lista completa — nunca vazio (incremento B do I-10).
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_homonimo_de_outro_estado_nao_entra(self):
        Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju SP', cidade='ITAMARAJU',
            estado='SP', cns='140162',
        )
        extracao = self._com_cartorio_sem_candidatos()
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_uf_por_sigla_filtra_homonimo_de_outro_estado(self):
        Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju SP', cidade='ITAMARAJU',
            estado='SP', cns='140163',
        )
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU - BA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('ITAMARAJU', 'BA'),
        )
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_comarca_com_hifen_interno_e_uf(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE XIQUE-XIQUE - BA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('XIQUE-XIQUE', 'BA'),
        )

    def test_comarca_com_hifen_interno_sem_uf(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE XIQUE-XIQUE\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('XIQUE-XIQUE', None),
        )

    def test_comarca_estado_por_extenso(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('ITAMARAJU', 'BA'),
        )

    def test_comarca_uf_por_barra(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE BOM JESUS DA LAPA/BA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('BOM JESUS DA LAPA', 'BA'),
        )

    def test_comarca_hifenizada_busca_cartorio_da_cidade(self):
        xique = Cartorios.objects.create(
            nome='Registro de Imóveis de Xique-Xique', cidade='XIQUE-XIQUE',
            estado='BA', cns='140165',
        )
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE XIQUE-XIQUE - BA\nMatrícula 1\n'
        )
        self.assertEqual(self._candidatos(extracao), [xique.pk])

    def test_duas_comarcas_hifenizadas_sao_ambiguas(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE XIQUE-XIQUE - BA\nCOMARCA DE ITAMARAJU - BA\n'
        )
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_match_unico_por_nome_de_outro_estado_nao_vira_candidato(self):
        Cartorios.objects.create(
            nome='Cartório Único SP', cidade='ITAMARAJU', estado='SP',
            cns='140164',
        )
        extracao = self._com_cartorio_sem_candidatos()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            raw='Cartório Único SP', normalized='Cartório Único SP',
        )
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_mesma_cidade_com_ufs_diferentes_e_ambigua(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE BOM JESUS - PIAUÍ\nCOMARCA DE BOM JESUS - GOIÁS\n'
        )
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        # Ambígua não vira comarca: o seletor cai na lista completa.
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_duas_comarcas_no_cabecalho_sao_ambiguas(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU - BA\nCOMARCA DE PRADO - BA\n'
        )
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_municipio_de_nao_e_comarca(self):
        extracao = self._com_cartorio_sem_candidatos(
            'MUNICÍPIO DE ITAMARAJU\n'
        )
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_sem_comarca_e_sem_valor_devolve_lista_completa(self):
        extracao = self._com_cartorio_sem_candidatos('Sem cabeçalho útil.')
        ids = self._candidatos(extracao)
        self.assertTrue(ids)
        self.assertLessEqual(len(ids), revisao.LIMITE_CARTORIOS_TODOS)
        self.assertEqual(ids, self._lista_completa())
        self.assertEqual(
            ids,
            IndiceCartorios().ids_de_todos(revisao.LIMITE_CARTORIOS_TODOS),
        )

    def test_cidade_fora_do_indice_cai_para_os_cartorios_da_uf(self):
        campinas = Cartorios.objects.create(
            nome='Registro de Imóveis de Campinas', cidade='CAMPINAS',
            estado='SP', cns='140165',
        )
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        comarca = revisao.comarca_do_documento(extracao)
        self.assertEqual(comarca, revisao.Comarca('EUNÁPOLIS', 'BA'))
        ids = self._candidatos(extracao)
        self.assertTrue(ids)
        self.assertNotIn(campinas.pk, ids)
        # Estágio de UF: só cartórios da BA, por (nome, id).
        self.assertEqual(ids, [self.itamaraju.pk, self.outro.pk])

    def test_uf_desconhecida_cai_para_a_lista_completa(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE CIDADE FANTASIA\nMatrícula 1\n'
        )
        comarca = revisao.comarca_do_documento(extracao)
        self.assertEqual(comarca, revisao.Comarca('CIDADE FANTASIA', None))
        self.assertEqual(self._candidatos(extracao), self._lista_completa())

    def test_ids_da_uf_ordena_por_nome_e_id_e_limita(self):
        zulu = Cartorios.objects.create(
            nome='Cartório Zulu', cidade='EUNÁPOLIS', estado='BA',
            cns='140166',
        )
        homonimo_um = Cartorios.objects.create(
            nome='A Cartório Homônimo', cidade='ITAMARAJU', estado='BA',
            cns='140167',
        )
        homonimo_dois = Cartorios.objects.create(
            nome='A Cartório Homônimo', cidade='PRADO', estado='BA',
            cns='140168',
        )
        campinas = Cartorios.objects.create(
            nome='Cartório Paulista', cidade='CAMPINAS', estado='SP',
            cns='140165',
        )
        indice = IndiceCartorios()
        esperado = [
            homonimo_um.pk, homonimo_dois.pk, zulu.pk,
            self.itamaraju.pk, self.outro.pk,
        ]
        self.assertEqual(indice.ids_da_uf('BA'), esperado)
        self.assertEqual(indice.ids_da_uf('BA', limite=3), esperado[:3])
        # SP inclui o cartório da fixture base ('CRI Teste …' < 'Cartório
        # Paulista' na ordenação por nome).
        self.assertEqual(
            indice.ids_da_uf('SP'),
            [self.documento.cartorio_id, campinas.pk],
        )
        self.assertEqual(indice.ids_da_uf(None), [])

    def test_ids_de_todos_ordena_por_nome_e_id_e_limita(self):
        zulu = Cartorios.objects.create(
            nome='Cartório Zulu', cidade='EUNÁPOLIS', estado='BA',
            cns='140166',
        )
        paulista = Cartorios.objects.create(
            nome='Cartório Paulista', cidade='CAMPINAS', estado='SP',
            cns='140165',
        )
        indice = IndiceCartorios()
        esperado = [
            self.documento.cartorio_id, paulista.pk, zulu.pk,
            self.itamaraju.pk, self.outro.pk,
        ]
        self.assertEqual(indice.ids_de_todos(), esperado)
        self.assertEqual(indice.ids_de_todos(limite=2), esperado[:2])

    def test_candidatos_preexistentes_sao_devolvidos(self):
        extracao = self._com_cartorio_sem_candidatos()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            match_candidatos=[self.outro.pk],
        )
        self.assertEqual(
            self._candidatos(extracao), [self.outro.pk],
        )

    def test_tela_lista_opcao_sem_preselecionar(self):
        extracao = self._com_cartorio_sem_candidatos()
        html = self._tela().content.decode()
        card = next(
            c for c in _elementos(html, 'article', presentes=('data-campo',))
            if _atributos(c)['data-chave'] == CHAVE
        )
        select = _descendentes(card, 'select', 'data-ocr-escolha')[0]
        opcoes = [
            o for o in _descendentes(select, 'option', 'value')
            if _atributos(o)['value']
        ]
        self.assertEqual(
            [_atributos(o)['value'] for o in opcoes], [str(self.itamaraju.pk)],
        )
        self.assertTrue(all('selected' not in _atributos(o) for o in opcoes))
        # Exibição apenas: nada foi gravado.
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertIsNone(campo.cartorio_escolhido_id)

    def _salvar(self, extracao, cartorio_id):
        html = self._tela().content.decode()
        toolbar = _elementos(html, 'div', presentes=('data-ocr-toolbar',))[0]
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': _atributos(toolbar)['data-versao'],
                'decisoes': [{
                    'chave': CHAVE, 'incluir': True,
                    'escolha': {
                        'pessoa_id': None, 'cartorio_id': cartorio_id,
                        'criar_novo': False,
                    },
                }],
            }),
            content_type='application/json',
        )

    def test_save_aceita_id_do_fallback_e_persiste_candidatos(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [self.itamaraju.pk])
        self.assertEqual(campo.cartorio_escolhido_id, self.itamaraju.pk)

    def test_save_aceita_escolha_vinda_do_estagio_de_uf(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        # O fallback gravado é o do estágio de UF: só cartórios da BA.
        self.assertEqual(
            campo.match_candidatos, [self.itamaraju.pk, self.outro.pk],
        )
        self.assertEqual(campo.cartorio_escolhido_id, self.outro.pk)

    def test_save_recusa_id_fora_do_fallback(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(
            extracao.campos.get(chave=CHAVE).match_candidatos, [],
        )
