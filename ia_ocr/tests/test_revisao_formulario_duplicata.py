"""Aceite c4: duplicata no formulário preserva o ato e importa atomicamente."""

from datetime import date
from unittest import mock

from dominial.models import (
    Documento, DocumentoImportado, DocumentoTipo, Imovel, Lancamento,
)
from ia_ocr.models import ImportacaoIA

from .payloads_extracao import payload_averbacao
from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, _Formulario, post_do_html,
)


def post_da_confirmacao(resposta):
    """POST que o navegador enviaria da página de confirmação renderizada."""
    html = resposta.content.decode()
    inicio = html.index('<!-- Enviar todos os documentos da cadeia -->')
    inicio_formulario = html.rfind('<form ', 0, inicio)
    html = html[:inicio_formulario] + html[inicio_formulario:].replace(
        '<form ', '<form id="lancamento-form" ', 1,
    )
    formulario = _Formulario()
    formulario.feed(html)
    return formulario.post()


class DuplicataFormularioTest(RevisaoFormularioBase):
    def _resultado_duplicata(self):
        return {
            'tipo': 'duplicata_encontrada',
            'duplicata_info': {
                'tem_duplicata': True,
                'acessivel': True,
                'documento_origem': mock.Mock(),
                'documentos_importaveis': [],
                'cadeia_dominial': [],
            },
        }, 'Duplicata encontrada.'

    def _preparar_duplicata(self, *, averbacao=False, **trocas):
        """Cria a duplicata e devolve a página de confirmação real."""
        tipo_origem = DocumentoTipo.objects.create(tipo='transcricao')
        cartorio_origem = self._cartorio('CRI de origem c4')
        imovel_origem = Imovel.objects.create(
            nome='Imóvel da cadeia c4', matricula='M-c4',
            terra_indigena_id=self.imovel.terra_indigena_id,
            proprietario=self.imovel.proprietario, cartorio=self.imovel.cartorio,
        )
        anterior = Documento.objects.create(
            imovel=imovel_origem, tipo=tipo_origem, numero='T365',
            data=date(1990, 1, 1), cartorio=cartorio_origem, livro='1', folha='1',
        )
        origem = Documento.objects.create(
            imovel=imovel_origem, tipo=tipo_origem, numero='T366',
            data=date(1991, 1, 1), cartorio=cartorio_origem, livro='1', folha='2',
        )
        Lancamento.objects.create(
            documento=origem, tipo=self.tipo_registro, numero_lancamento='R1 T366',
            data=date(1992, 1, 1), origem='T365', cartorio_origem=cartorio_origem,
        )

        payload = self._payload_de_tres_atos()
        if averbacao:
            payload['acts'][0] = payload_averbacao(self.job.job_id)['acts'][0]
            payload['acts'][0]['area'] = {
                'raw': '120,00 m2', 'normalized': '120', 'confianca': .95,
                'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': '120,00 m2'}, 'unidade': 'm2',
            }
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo(cartorio_origem.nome, 'CRI de Guaíra'),
            'livro': self._campo('', 'Livro 2-RG'),
            'folha': self._campo('', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=cartorio_origem,
        )
        pagina = self.client.get(self.url_ato(0))
        confirmacao = self.client.post(
            self.url_ato(0), post_do_html(pagina, **trocas),
        )
        self.assertTemplateUsed(confirmacao, 'dominial/duplicata_importacao.html')
        return confirmacao

    def test_c4_duplicata_mostra_template_da_revisao_sem_gravar_e_guarda_rascunho(self):
        antes = self.contagens()
        pagina = self.client.get(self.url_ato(0))
        with mock.patch(
            'ia_ocr.revisao_ato.LancamentoService.criar_lancamento_completo',
            return_value=self._resultado_duplicata(),
        ), mock.patch(
            'ia_ocr.views.revisar_extras.LancamentoDuplicataService.obter_dados_duplicata_para_template',
            return_value={'documento_origem': {}, 'cadeia_dominial': []},
        ):
            resposta = self.client.post(
                self.url_ato(0), post_do_html(pagina, observacoes='digitado'),
            )

        self.assertTemplateUsed(resposta, 'dominial/duplicata_importacao.html')
        self.assertEqual(self.contagens(), antes)
        self.assertIn('revisar/0/duplicata/', resposta.content.decode())
        rascunho = self.client.session['ia_ocr_rascunhos'][str(self.extracao.pk)]['0']
        self.assertEqual(rascunho['observacoes'], ['digitado'])

    def test_c4_cancelar_volta_ao_ato_com_o_digitado(self):
        pagina = self.client.get(self.url_ato(0))
        with mock.patch(
            'ia_ocr.revisao_ato.LancamentoService.criar_lancamento_completo',
            return_value=self._resultado_duplicata(),
        ), mock.patch(
            'ia_ocr.views.revisar_extras.LancamentoDuplicataService.obter_dados_duplicata_para_template',
            return_value={'documento_origem': {}, 'cadeia_dominial': []},
        ):
            self.client.post(self.url_ato(0), post_do_html(pagina, observacoes='digitado'))

        volta = self.client.get(self.url_ato(0))
        self.assertIn('digitado', volta.content.decode())

    def test_c4_falha_depois_da_importacao_desfaz_tudo(self):
        confirmacao = self._preparar_duplicata()
        post = post_da_confirmacao(confirmacao)
        antes = (Lancamento.objects.count(), ImportacaoIA.objects.count())
        self.assertFalse(DocumentoImportado.objects.exists())
        from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService
        with mock.patch.object(
            ImportacaoCadeiaService, 'marcar_documento_importado',
            wraps=ImportacaoCadeiaService.marcar_documento_importado,
        ) as marcar, mock.patch(
            'ia_ocr.views.revisar_extras.revisao_ato.salvar_ato',
            side_effect=RuntimeError('falha'),
        ):
            resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(resposta.status_code, 302)
        marcar.assert_called()
        self.assertFalse(DocumentoImportado.objects.exists())
        self.assertEqual((Lancamento.objects.count(), ImportacaoIA.objects.count()), antes)

    def test_c4_cadeia_parcial_desfaz_tudo(self):
        # Prova M3: serviço que diz sucesso mas devolve erro desfaz a importação
        # inteira — nada de lançamento, auditoria ou documento importado.
        confirmacao = self._preparar_duplicata()
        post = post_da_confirmacao(confirmacao)
        with mock.patch(
            'ia_ocr.views.revisar_extras.LancamentoDuplicataService.processar_importacao_duplicata',
            return_value={
                'sucesso': True,
                'documentos_importados': 1,
                'erros': ['Erro ao importar documento'],
                'mensagem': 'Importação concluída',
            },
        ):
            resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Lancamento.objects.filter(documento=self.documento).exists())
        self.assertFalse(ImportacaoIA.objects.filter(ocr_job=self.job).exists())
        self.assertFalse(DocumentoImportado.objects.exists())

    def test_c4_ato_ja_salvo_nao_reimporta(self):
        # Prova M4: repetir o POST de confirmação (duplo clique) não reimporta a
        # cadeia e avisa que o ato já foi salvo.
        confirmacao = self._preparar_duplicata()
        post = post_da_confirmacao(confirmacao)
        primeira = self.client.post(self.url_ato(0) + 'duplicata/', post)
        self.assertTrue(
            Lancamento.objects.filter(documento=self.documento).exists(),
            self.mensagens(primeira),
        )
        documentos_importados = DocumentoImportado.objects.count()
        importacoes = ImportacaoIA.objects.filter(ocr_job=self.job).count()

        resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(DocumentoImportado.objects.count(), documentos_importados)
        self.assertEqual(
            ImportacaoIA.objects.filter(ocr_job=self.job).count(), importacoes,
        )
        self.assertIn(
            'já foi salvo', ' '.join(self.mensagens(resposta)).lower(),
        )

    def test_c4_confirmacao_preserva_area_descartada_e_forma_averbacao(self):
        confirmacao = self._preparar_duplicata(
            averbacao=True, descartar_area='1', forma_averbacao='Construção',
        )
        post = post_da_confirmacao(confirmacao)
        html = confirmacao.content.decode()

        self.assertIn('name="descartar_area" value="1"', html)
        self.assertIn('name="forma_averbacao" value="Construção"', html)
        resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertTrue(
            Lancamento.objects.filter(documento=self.documento).exists(),
            self.mensagens(resposta),
        )
        self.assertEqual(Lancamento.objects.get(documento=self.documento).forma, 'Construção')

    def test_c4_formulario_manual_nao_muda(self):
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        from django.urls import reverse

        request = RequestFactory().get('/')
        request.user = self.usuario
        html = render_to_string('dominial/duplicata_importacao.html', {
            'tis': self.imovel.terra_indigena_id,
            'imovel': self.imovel,
            'documento': self.documento,
            'duplicata_info': {'documento_origem': {'id': 1}, 'cadeia_dominial': []},
        }, request=request)

        action = reverse('importar_duplicata', args=(
            self.imovel.terra_indigena_id.pk, self.imovel.pk, self.documento.pk,
        ))
        self.assertIn(f'<form method="post" action="{action}">', html)
