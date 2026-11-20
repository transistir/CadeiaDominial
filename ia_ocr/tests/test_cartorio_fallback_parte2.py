"""Parte do corpo de ``CartorioFallbackTest``; coletada pela fachada."""

from dominial.models import Cartorios
from ia_ocr import revisao

from .test_cartorio_fallback_base import CABECALHO, CHAVE


class CartorioFallbackTestParte2:
    def test_save_aceita_id_do_fallback_sem_gravar_candidatos(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertEqual(campo.cartorio_escolhido_id, self.itamaraju.pk)


    def test_save_aceita_escolha_vinda_do_estagio_de_uf(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        # Nada é gravado (#318): persistir a lista do estágio de UF (sem
        # corte) envelheceria milhares de ids no JSON, e congelar só a
        # escolha fechava o seletor na troca de cartório. O que a tela usa
        # é o ``cartorio_escolhido_id``; o fallback o GET recalcula.
        self.assertEqual(campo.match_candidatos, [])
        self.assertEqual(campo.cartorio_escolhido_id, self.outro.pk)


    def test_uf_com_501_cartorios_inclui_o_ultimo_no_seletor_e_no_save(self):
        alvo = self._povoar_501_na_uf()
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        ids = self._candidatos(extracao)
        # Sem a cidade da comarca no índice, o estágio de UF devolve TODA
        # a BA: o cartório na posição 501 não pode sumir.
        self.assertEqual(len(ids), 501)
        self.assertEqual(ids[-1], alvo.pk)
        resposta = self._salvar(extracao, alvo.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertEqual(campo.cartorio_escolhido_id, alvo.pk)


    def test_sem_comarca_501_cartorios_inclui_o_ultimo_no_seletor_e_no_save(self):
        alvo = self._povoar_501_no_total()
        extracao = self._com_cartorio_sem_candidatos('Sem cabeçalho útil.')
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        ids = self._candidatos(extracao)
        # Pior caso (cabeçalho ilegível): lista completa sem corte — o
        # último do índice continua escolhível e aceito no save.
        self.assertEqual(len(ids), 501)
        self.assertEqual(ids[-1], alvo.pk)
        resposta = self._salvar(extracao, alvo.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertEqual(campo.cartorio_escolhido_id, alvo.pk)


    def test_estagio_da_cidade_corta_em_20(self):
        Cartorios.objects.bulk_create(
            Cartorios(
                nome=f'A Cartório de Itamaraju {i:02d}', cidade='ITAMARAJU',
                estado='BA', cns=f'9200{i:05d}',
            )
            for i in range(1, 21)
        )
        extracao = self._com_cartorio_sem_candidatos(CABECALHO)
        ids = self._candidatos(extracao)
        # A cidade da comarca continua cortada em 20 (comportamento
        # mantido): os 'A …' precedem 'Registro de Imóveis …' na ordem,
        # então o cartório da fixture fica fora do corte.
        self.assertEqual(len(ids), revisao.LIMITE_CANDIDATOS_FALLBACK)
        self.assertNotIn(self.itamaraju.pk, ids)


    def test_save_recusa_id_fora_do_fallback(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(
            extracao.campos.get(chave=CHAVE).match_candidatos, [],
        )


    def test_segundo_save_pode_trocar_de_cartorio(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        primeira = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(primeira.status_code, 200, primeira.content)
        segunda = self._salvar(extracao, self.outro.pk)
        self.assertEqual(segunda.status_code, 200, segunda.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.cartorio_escolhido_id, self.outro.pk)


    def test_get_depois_do_save_continua_listando_o_fallback(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        resposta = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        # Trocar de cartório depende do seletor continuar oferecendo o
        # fallback inteiro depois de uma escolha salva.
        self.assertEqual(
            self._opcoes_cartorio(),
            [str(self.itamaraju.pk), str(self.outro.pk)],
        )


    def test_save_nao_persiste_a_lista_do_fallback(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        # Nada de lista congelada no banco: sem corte, a lista inteira do
        # estágio de UF (milhares de ids) inflaria o JSON de cada campo.
        self.assertLessEqual(len(campo.match_candidatos), 1)


    def test_segundo_save_recusa_id_fora_do_fallback(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE EUNÁPOLIS - ESTADO DA BAHIA\nMatrícula 1\n'
        )
        primeira = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(primeira.status_code, 200, primeira.content)
        # O cartório do documento da fixture é SP: fora do fallback da BA.
        resposta = self._salvar(extracao, self.documento.cartorio_id)
        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(
            extracao.campos.get(chave=CHAVE).cartorio_escolhido_id,
            self.itamaraju.pk,
        )

