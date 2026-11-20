"""Parte do corpo de ``CartorioFallbackTest``; coletada pela fachada."""

from dominial.models import Cartorios
from ia_ocr import revisao
from ia_ocr.models import CampoSugerido
from ia_ocr.revisao import IndiceCartorios

from .test_cartorio_fallback_base import CHAVE


class CartorioFallbackTestParte1:
    def test_comarca_do_cabecalho_inclui_cartorio_da_cidade(self):
        extracao = self._com_cartorio_sem_candidatos()
        ids = self._candidatos(extracao)
        self.assertEqual(ids, [self.itamaraju.pk])


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


    def test_comarca_uf_colada_por_hifen_sigla(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU-BA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('ITAMARAJU', 'BA'),
        )


    def test_comarca_uf_colada_por_hifen_estado_por_extenso(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU-BAHIA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('ITAMARAJU', 'BA'),
        )


    def test_comarca_hifenizada_com_uf_colada(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE XIQUE-XIQUE-BA\nMatrícula 1\n'
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


    def test_comarca_uf_colada_busca_cartorio_da_cidade(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU-BA\nMatrícula 1\n'
        )
        # UF colada não pode virar "cidade" ITAMARAJU-BA (fora do índice):
        # o cartório de ITAMARAJU sai, não a lista completa.
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])


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
        self.assertEqual(ids, self._lista_completa())
        self.assertEqual(ids, IndiceCartorios().ids_de_todos())


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
        # #341 fase 3: o fallback é cálculo de exibição (o GET da tela
        # oferecia a lista sem pré-seleção e sem gravar nada) — resolvido
        # direto no resolvedor agora que a tela se foi.
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertIsNone(campo.cartorio_escolhido_id)

