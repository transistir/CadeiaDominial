"""Entrega do app, item 2: origem com nome mas sem ``cartorio_origem[]``.

O prefill manda o nome lido quando não há cadastro escolhido; o POST leva
``cartorio_origem[]`` vazio e ``cartorio_origem_nome[]`` preenchido. A
verificação de duplicata precisa resolver o ID pelo MESMO fallback de nome
da gravação — sem inventar cartório — antes de decidir se a cadeia já existe.

A confirmação da importação relê os mesmos campos preservados pelo POST
original; se ela ignorasse o nome, a tela ofereceria a duplicata e o
"confirmar" falharia. Os testes abaixo cobrem o fluxo real GET → tela de
duplicata → POST de confirmação e o bloqueio de data antes de importar.
"""

from datetime import date
from unittest import mock

from dominial.models import (
    Cartorios, Documento, DocumentoTipo, Imovel, Lancamento,
)
from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService
from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService
from ia_ocr.revisao_ato.bloqueios import MENSAGEM_DATA_ABERTURA

from .payloads_extracao import payload_m237_abertura
from .test_revisao_abertura_m237 import AberturaM237Base
from .test_revisao_formulario_duplicata import post_da_confirmacao


class _OrigemSoNomeBase(AberturaM237Base):
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

    def _pagina_da_duplicata(self):
        """POST com nome de cartório e ID vazio → tela de confirmação real."""
        self._cartorio_e_origem_em_outra_cadeia()
        pagina = self.client.get(self.url_ato(0))
        self.assertEqual(pagina.status_code, 200)
        resposta = self.client.post(
            self.url_ato(0), self._post_sem_id_de_cartorio(pagina),
        )
        self.assertTemplateUsed(resposta, 'dominial/duplicata_importacao.html')
        return resposta

    @staticmethod
    def _post_sem_id_de_cartorio(pagina):
        from .test_revisao_formulario_view_base import post_do_html

        dados = post_do_html(pagina)
        dados['cartorio_origem[]'] = ['']
        dados['cartorio_origem_nome[]'] = ['CRI de Itamaraju']
        return dados


class CartorioOrigemSoNomeTest(_OrigemSoNomeBase):
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


class ConfirmacaoDuplicataOrigemNomeTest(_OrigemSoNomeBase):
    def test_confirmacao_reenvia_nome_e_conclui_importacao(self):
        confirmacao = self._pagina_da_duplicata()
        antes = Lancamento.objects.filter(documento=self.documento).count()

        resposta = self.client.post(
            self.url_ato(0) + 'duplicata/', post_da_confirmacao(confirmacao),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento).count(),
            antes + 1,
            self.mensagens(resposta),
        )

    def test_confirmacao_com_id_vazio_resolve_nome_no_validar(self):
        # Sem o ID resolvido por ``_campos_preservados``: o POST de
        # confirmação chega com ``cartorio_origem[]`` vazio e só o nome.
        confirmacao = self._pagina_da_duplicata()
        post = post_da_confirmacao(confirmacao)
        post['cartorio_origem[]'] = ['']
        post['cartorio_origem_nome[]'] = ['CRI de Itamaraju']
        validacoes = []
        original = LancamentoDuplicataService._validar_identidade_duplicata

        def validar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            validacoes.append(resultado)
            return resultado

        with mock.patch.object(
            LancamentoDuplicataService, '_validar_identidade_duplicata',
            side_effect=validar,
        ):
            self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(len(validacoes), 1)
        self.assertTrue(validacoes[0]['sucesso'], validacoes[0])


class AberturaSemDataNaConfirmacaoDuplicataTest(_OrigemSoNomeBase):
    def test_sem_data_na_confirmacao_bloqueia_antes_de_gravar(self):
        confirmacao = self._pagina_da_duplicata()
        post = post_da_confirmacao(confirmacao)
        post['data'] = ['']
        antes = self.contagens()

        with mock.patch.object(
            ImportacaoCadeiaService, 'marcar_documento_importado',
            wraps=ImportacaoCadeiaService.marcar_documento_importado,
        ) as marcar:
            resposta = self.client.post(
                self.url_ato(0) + 'duplicata/', post,
            )

        self.assertEqual(resposta.status_code, 302)
        marcar.assert_not_called()
        self.assertIn(
            MENSAGEM_DATA_ABERTURA, '\n'.join(self.mensagens(resposta)),
        )
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists()
        )
