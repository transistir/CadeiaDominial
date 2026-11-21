"""MUST-FIX do review do Codex no ZIP "Baixar certidões" (#334).

Em módulo próprio: com esses testes dentro,
``test_documento_digital_certidoes.py`` ficaria acima do teto de 400
linhas imposto pelo CI. A cadeia base vem de ``_BaseCadeiaCertidoes``.
"""

import json
import re
import tempfile
from datetime import date
from unittest import mock

from django.urls import reverse

from dominial.models import Documento, Imovel, Lancamento, UserImovel
from dominial.services.cadeia_dominial_tabela_service import (
    CadeiaDominialTabelaService,
)
from dominial.tests.test_documento_digital_certidoes import _BaseCadeiaCertidoes


def _cadeia_com_dois_homonimos(cls):
    """M12345 passa a citar duas origens reais (T50 e T40).

    Complementa ``_BaseCadeiaCertidoes``: T40 vive no imóvel de origem,
    ao lado de T50, e o lançamento da matrícula cita os dois. Sem escolha,
    a cadeia segue T50 (padrão: maior número entre irmãos).
    """
    cls.doc_t40 = Documento.objects.create(
        imovel=cls.imovel_origem,
        tipo=cls.tipo_transcricao,
        numero='T40',
        data=date(2019, 3, 3),
        cartorio=cls.cartorio,
        livro='2',
        folha='4',
    )
    Lancamento.objects.bulk_create([
        Lancamento(
            documento=cls.doc_t40,
            tipo=cls.tipo_inicio,
            data=date(2019, 3, 3),
            cartorio_origem=cls.cartorio,
            origem='',
        ),
    ])
    # `.update()` não dispara signal de origens estruturadas: a leitura
    # fica no fallback textual, com o cartório do próprio lançamento.
    Lancamento.objects.filter(documento=cls.doc_matricula).update(
        origem='T50; T40'
    )


class EscolhaDeOrigemNoZipTest(_BaseCadeiaCertidoes):
    """MF1: o ZIP segue a origem escolhida na sessão, como a tela.

    M12345 passa a citar duas origens reais (T50 e T40). Sem escolha, a
    cadeia segue T50 (padrão: maior número entre irmãos); com
    ``origem_documento_<id> = 'T40'`` na sessão — o mesmo mecanismo que os
    botões de origem da tela gravam (#201) — o ZIP tem que seguir T40.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _cadeia_com_dois_homonimos(cls)

    def test_zip_segue_a_origem_escolhida_na_sessao(self):
        self._criar_pdf(self.doc_origem, 'pdf-t50.pdf', b'%PDF-1.4 t50')
        self._criar_pdf(self.doc_t40, 'pdf-t40.pdf', b'%PDF-1.4 t40')

        # Sem escolha na sessão: o tronco segue T50.
        self.assertEqual(
            self._nomes_do_zip(self.client.get(self._url())),
            ['02_Transcricao_T50_pdf-t50.pdf'],
        )

        session = self.client.session
        session[f'origem_documento_{self.doc_matricula.id}'] = 'T40'
        session.save()

        # A tela segue T40 — é esta lista que o ZIP tem que espelhar:
        linhas = CadeiaDominialTabelaService(
            user=self.user
        ).get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id, self.client.session
        )['cadeia']
        self.assertEqual(
            [item['documento'].numero for item in linhas], ['M12345', 'T40']
        )

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._nomes_do_zip(response),
            ['02_Transcricao_T40_pdf-t40.pdf'],
        )


class SanitizacaoDoNumeroNoZipTest(_BaseCadeiaCertidoes):
    """MF2: o número do documento não pode virar caminho dentro do ZIP."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.imovel_barra = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imovel Barra 334',
            proprietario=cls.proprietario,
            matricula='M123/45',
            cartorio=cls.cartorio,
        )
        cls.doc_barra = Documento.objects.create(
            imovel=cls.imovel_barra,
            tipo=cls.tipo_matricula,
            numero='M123/45',
            data=date(2024, 2, 2),
            cartorio=cls.cartorio,
            livro='1',
            folha='2',
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_barra)
        cls.imovel_pontos = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imovel Pontos 334',
            proprietario=cls.proprietario,
            matricula='../evil',
            cartorio=cls.cartorio,
        )
        cls.doc_pontos = Documento.objects.create(
            imovel=cls.imovel_pontos,
            tipo=cls.tipo_matricula,
            numero='../evil',
            data=date(2024, 3, 3),
            cartorio=cls.cartorio,
            livro='1',
            folha='3',
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_pontos)

    def _url_de(self, imovel):
        return reverse('baixar_certidoes_cadeia', kwargs={
            'tis_id': self.tis.id, 'imovel_id': imovel.id,
        })

    def test_numero_com_barra_nao_cria_subpasta(self):
        """`M123/45` vira `M123_45`: nome plano, sem separador de caminho."""
        self._criar_pdf(self.doc_barra, 'certidao.pdf')

        response = self.client.get(self._url_de(self.imovel_barra))

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        self.assertEqual(nomes, ['01_Matricula_M123_45_certidao.pdf'])

    def test_numero_com_pontos_nao_sobe_de_nivel(self):
        """`../evil` não sobra `..` nem `/` no nome dentro do ZIP."""
        self._criar_pdf(self.doc_pontos, 'certidao.pdf')

        response = self.client.get(self._url_de(self.imovel_pontos))

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        self.assertEqual(len(nomes), 1, nomes)
        self.assertFalse(
            any('/' in nome or '\\' in nome or '..' in nome for nome in nomes),
            nomes,
        )
        # `../evil` → `__evil`: os dois pontos viram `_` e o `/` também.
        self.assertEqual(nomes, ['01_Matricula___evil_certidao.pdf'])


class FalhaDuranteACopiaTest(_BaseCadeiaCertidoes):
    """MF3: OSError na cópia não pode virar ZIP truncado com 200."""

    def test_falha_na_copia_nao_entrega_zip_truncado(self):
        self._criar_pdf(self.doc_matricula, 'quebra.pdf', b'%PDF-1.4 real')

        with (
            mock.patch(
                'dominial.views.certidoes_views.shutil.copyfileobj',
                side_effect=OSError('falha de leitura durante a cópia'),
            ),
            self.assertLogs(
                'dominial.views.certidoes_views', level='ERROR'
            ) as logs,
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('application/zip', response.get('Content-Type', ''))
        self.assertEqual(
            response.url,
            reverse('tronco_principal', kwargs={
                'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            }),
        )
        self.assertTrue(
            any('certidões' in log for log in logs.output), logs.output
        )
        # A mensagem de erro chega na cadeia — sem JSON/ZIP parcial:
        seguida = self.client.get(response.url)
        self.assertContains(seguida, 'Erro ao gerar o ZIP')


class SomenteRegistrosFantasmaTest(_BaseCadeiaCertidoes):
    """MF4: registro sem arquivo físico não entra na conta do "tem PDF"."""

    def test_somente_fantasma_redireciona_com_mensagem(self):
        """Só registro fantasma → 302 com MENSAGEM_SEM_PDF, sem ZIP."""
        self._criar_registro_fantasma(
            self.doc_matricula,
            'fantasma.pdf',
            'documentos_digitais/2024/01/fantasma.pdf',
        )

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('tronco_principal', kwargs={
                'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            }),
        )
        seguida = self.client.get(response.url)
        self.assertContains(
            seguida, 'Nenhum PDF anexado aos documentos desta cadeia.'
        )


class SpoolFechadoEmErroTest(_BaseCadeiaCertidoes):
    """MF5: o spool fecha em qualquer caminho de exceção."""

    def test_spool_fechado_quando_a_resposta_falha(self):
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')
        criados = []
        spool_real = tempfile.SpooledTemporaryFile

        def _spool_espiao(*args, **kwargs):
            criados.append(spool_real(*args, **kwargs))
            return criados[-1]

        with (
            mock.patch(
                'dominial.views.certidoes_views.tempfile.SpooledTemporaryFile',
                side_effect=_spool_espiao,
            ),
            mock.patch(
                'dominial.views.certidoes_views.FileResponse',
                side_effect=RuntimeError('falha na construção da resposta'),
            ),
            self.assertLogs('dominial.views.certidoes_views', level='ERROR'),
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(criados), 1, criados)
        self.assertTrue(criados[0].closed)


class EscolhasDaUrlNoZipTest(_BaseCadeiaCertidoes):
    """MF1 (2ª rodada): o link do ZIP leva o ``?escolhas`` da URL.

    A tela (``tronco_principal``) aceita
    ``?escolhas={"<doc>":"documento:<origem>"}`` e SUBSTITUI a sessão —
    inclusive ``{}``, que limpa. O botão "Baixar certidões" tem que levar o
    parâmetro no href e a view do ZIP interpretá-lo com a mesma precedência
    da tela (param > sessão, inclusive vazio): senão, sessão em T50 + URL
    escolhendo T40 mostra T40 e o clique baixa T50.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _cadeia_com_dois_homonimos(cls)

    def _url_cadeia(self):
        return reverse('tronco_principal', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
        })

    def _prender_sessao(self, numero):
        session = self.client.session
        session[f'origem_documento_{self.doc_matricula.id}'] = numero
        session.save()

    def _com_pdfs_t50_e_t40(self):
        self._criar_pdf(self.doc_origem, 'pdf-t50.pdf', b'%PDF-1.4 t50')
        self._criar_pdf(self.doc_t40, 'pdf-t40.pdf', b'%PDF-1.4 t40')

    def test_link_do_zip_na_tela_leva_escolhas_da_url(self):
        """tela → href → ZIP: o galho escolhido na URL é o baixado."""
        self._com_pdfs_t50_e_t40()
        self._prender_sessao('T50')

        escolhas = json.dumps({
            str(self.doc_matricula.id): f'documento:{self.doc_t40.pk}'
        })
        tela = self.client.get(
            self._url_cadeia(), data={'escolhas': escolhas}
        )
        self.assertEqual(tela.status_code, 200)

        correspondencia = re.search(
            r'href="([^"]*certidoes\.zip[^"]*)"', tela.content.decode()
        )
        self.assertIsNotNone(correspondencia, 'botão do ZIP ausente na tela')
        response = self.client.get(correspondencia.group(1))

        self.assertEqual(response.status_code, 200)
        # A tela segue T40 (?escolhas > sessão): o ZIP baixa o mesmo galho —
        # e não o T50 preso na sessão.
        self.assertEqual(
            self._nomes_do_zip(response), ['02_Transcricao_T40_pdf-t40.pdf']
        )

    def test_escolhas_vazio_no_zip_iguala_sem_parametro(self):
        """``?escolhas={}`` no ZIP = GET sem o parâmetro (não 500)."""
        self._com_pdfs_t50_e_t40()
        self._prender_sessao('T50')

        sem_parametro = self._nomes_do_zip(self.client.get(self._url()))
        com_vazio = self.client.get(self._url(), data={'escolhas': '{}'})

        self.assertEqual(com_vazio.status_code, 200)
        self.assertEqual(self._nomes_do_zip(com_vazio), sem_parametro)
        self.assertEqual(sem_parametro, ['02_Transcricao_T50_pdf-t50.pdf'])

    def test_escolhas_nao_json_no_zip_nao_quebra(self):
        """``?escolhas=nao-e-json``: JSON inválido vira ``{}``, sem 500."""
        self._com_pdfs_t50_e_t40()
        self._prender_sessao('T50')

        response = self.client.get(
            self._url(), data={'escolhas': 'nao-e-json'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._nomes_do_zip(response), ['02_Transcricao_T50_pdf-t50.pdf']
        )

    def test_escolhas_vazio_descarta_a_sessao_nao_padrao(self):
        """Precedência param > sessão, inclusive vazio, como na tela.

        Sessão presa em T40 (não-padrão): sem parâmetro o ZIP segue T40;
        com ``?escolhas={}`` a sessão é descartada e volta o padrão T50.
        """
        self._com_pdfs_t50_e_t40()
        self._prender_sessao('T40')
        self.assertEqual(
            self._nomes_do_zip(self.client.get(self._url())),
            ['02_Transcricao_T40_pdf-t40.pdf'],
        )

        response = self.client.get(self._url(), data={'escolhas': '{}'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._nomes_do_zip(response), ['02_Transcricao_T50_pdf-t50.pdf']
        )
