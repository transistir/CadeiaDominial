"""Entrega do app, item 2: origem com nome mas sem ``cartorio_origem[]``.

O prefill manda o nome lido quando não há cadastro escolhido; o POST leva
``cartorio_origem[]`` vazio e ``cartorio_origem_nome[]`` preenchido. A
verificação de duplicata precisa resolver o ID pelo MESMO fallback de nome
da gravação — sem inventar cartório — antes de decidir se a cadeia já existe.
"""

from datetime import date

from dominial.models import (
    Cartorios, Documento, DocumentoTipo, Imovel, Lancamento,
)

from .payloads_extracao import payload_m237_abertura
from .test_revisao_abertura_m237 import AberturaM237Base


class CartorioOrigemSoNomeTest(AberturaM237Base):
    def _cartorio_e_origem_em_outra_cadeia(self):
        cartorio = Cartorios.objects.create(
            nome='CRI de Itamaraju', cns='CNS-ITAMARAJU', estado='BA',
        )
        outro_imovel = Imovel.objects.create(
            nome='Imóvel de outra cadeia',
            matricula='OUTRA-4321',
            terra_indigena_id=self.imovel.terra_indigena_id,
            proprietario=self.imovel.proprietario,
            cartorio=cartorio,
        )
        tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        Documento.objects.create(
            imovel=outro_imovel, tipo=tipo_transcricao, numero='4321',
            data=date(1990, 1, 1), cartorio=cartorio, livro='3', folha='12',
        )

        payload = payload_m237_abertura(self.job.job_id)
        payload['acts'][0]['origem']['cartorio'] = self._campo(
            cartorio.nome, 'CRI de Itamaraju',
        )
        self.extracao.delete()
        return self._aberta(payload)

    def test_origem_so_com_nome_resolve_cartorio_e_barra_duplicata(self):
        self._cartorio_e_origem_em_outra_cadeia()
        antes = self.contagens()

        pagina = self.client.get(self.url_ato(0))
        self.assertEqual(pagina.status_code, 200)
        resposta = self.client.post(
            self.url_ato(0), self._post_sem_id_de_cartorio(pagina),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'dominial/duplicata_importacao.html')
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists()
        )

    @staticmethod
    def _post_sem_id_de_cartorio(pagina):
        from .test_revisao_formulario_view_base import post_do_html

        dados = post_do_html(pagina)
        dados['cartorio_origem[]'] = ['']
        dados['cartorio_origem_nome[]'] = ['CRI de Itamaraju']
        return dados
