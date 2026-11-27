"""Cenários de salvar o ato (incluindo o rollback do erro interno) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_formulario_view.py`` (Etapa 12 do
plano de 400 linhas). Corpos e nomes de classes preservados.
"""

import re

from django.urls import reverse

from dominial.models import Lancamento
from ia_ocr.models import CampoSugerido, ImportacaoIA, OcrJobTransicao

from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase,
    post_do_html,
)


class SalvarAtoTest(RevisaoFormularioBase):
    def test_salvar_grava_um_lancamento_com_os_campos_do_prefill(self):
        antes = self.contagens()

        resposta = self.salvar(0)

        self.assertRedirects(resposta, self.url_ato(1), fetch_redirect_response=False)
        depois = self.contagens()
        self.assertEqual(depois['Lancamento'] - antes['Lancamento'], 1)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(lancamento.numero_lancamento, 'R1 M237')
        self.assertEqual(str(lancamento.data), '2020-02-15')
        self.assertEqual(str(lancamento.area), '12.5000')
        self.assertEqual(
            sorted(lancamento.pessoas.values_list('tipo', 'nome_digitado')),
            [
                ('adquirente', 'PEDRO SANTOS'),
                ('transmitente', 'JOÃO DA SILVA'),
                ('transmitente', 'MARIA DA SILVA'),
            ],
        )

    def test_vinculo_de_auditoria_no_formato_da_importacao(self):
        self.salvar(0)

        lancamento = Lancamento.objects.get(documento=self.documento)
        vinculo = ImportacaoIA.objects.get(modelo='Lancamento')
        self.assertEqual(vinculo.objeto_id, lancamento.pk)
        self.assertEqual(vinculo.lancamento, lancamento)
        self.assertEqual(vinculo.campo.chave, '/acts/0')
        self.assertEqual(vinculo.ocr_job, self.job)
        self.assertEqual(vinculo.criado_por, self.usuario)
        pessoas = ImportacaoIA.objects.filter(modelo='LancamentoPessoa')
        self.assertEqual(pessoas.count(), 3)
        self.assertEqual(
            sorted(pessoas.values_list('campo__chave', flat=True)),
            ['/acts/0/partes/0', '/acts/0/partes/1', '/acts/0/partes/2'],
        )

    def test_linhas_do_ato_ficam_importadas_e_as_outras_nao(self):
        self.salvar(0)

        status = dict(CampoSugerido.objects.filter(
            extracao=self.extracao, chave__in=('/acts/0/data', '/acts/1/data'),
        ).values_list('chave', 'status_revisao'))
        self.assertEqual(status, {
            '/acts/0/data': 'importado', '/acts/1/data': 'sugerido',
        })

    def test_segundo_ato_continua_pendente_e_a_sidebar_reflete(self):
        self.salvar(0)

        resposta = self.client.get(self.url_ato(1))

        html = resposta.content.decode()
        self.assertIn('ato 2 de 3', html)
        self.assertIn('1 de 3 salvo', html)
        self.assertIn('✔ salvo', html)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertIn(
            reverse('editar_lancamento', kwargs={
                'tis_id': self.imovel.terra_indigena_id.pk,
                'imovel_id': self.imovel.pk, 'lancamento_id': lancamento.pk,
            }),
            html,
        )
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_job_vira_revisado_no_primeiro_ato(self):
        self.salvar(0)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        self.assertTrue(OcrJobTransicao.objects.filter(
            ocr_job=self.job, para_status='revisado', motivo='revisao_formulario',
        ).exists())

    def test_ato_fora_de_ordem_e_permitido(self):
        resposta = self.salvar(2)

        # Depois do último, a volta ao primeiro pendente.
        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)
        self.assertEqual(
            ImportacaoIA.objects.get(modelo='Lancamento').campo.chave, '/acts/2',
        )
        self.assertEqual(
            Lancamento.objects.get(documento=self.documento).numero_lancamento,
            'R2 M237',
        )

    def test_ultimo_ato_conclui_a_revisao(self):
        self.salvar(2)
        self.salvar(0)
        resposta = self.salvar(1)

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)
        self.assertIn(
            '✅ Revisão concluída: todos os atos desta extração foram resolvidos.',
            self.mensagens(resposta),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 3)
        # E a entrada da revisão passa a levar ao documento.
        self.assertRedirects(
            self.client.get(self.url_entrada()), self.url_documento(),
            fetch_redirect_response=False,
        )

    def test_salvar_limpa_o_rascunho_do_ato(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(self.url_ato(0), post_do_html(pagina, _ir_para='1'))
        self.assertIn('0', self.client.session['ia_ocr_rascunhos'][str(self.extracao.pk)])

        self.salvar(0)

        self.assertNotIn(
            str(self.extracao.pk), self.client.session.get('ia_ocr_rascunhos', {}),
        )

    def test_get_de_ato_salvo_vai_para_a_edicao_do_lancamento(self):
        self.salvar(0)

        resposta = self.client.get(self.url_ato(0))

        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertRedirects(
            resposta,
            reverse('editar_lancamento', kwargs={
                'tis_id': self.imovel.terra_indigena_id.pk,
                'imovel_id': self.imovel.pk, 'lancamento_id': lancamento.pk,
            }),
            fetch_redirect_response=False,
        )


class AreaEmOutraUnidadeSalvarTest(RevisaoFormularioBase):
    """M3: área não-ha exige uma decisão explícita no POST que salva o ato."""

    def setUp(self):
        super().setUp()
        payload = self._payload_de_tres_atos()
        payload['acts'] = [payload['acts'][0]]
        payload['acts'][0]['area'] = {
            **self._campo('12.50', 'área 12,50 ha'),
            'unidade': 'alqueires',
            'raw': '12,50 alqueires',
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_area_preenchida_em_hectares_salva_e_importa_o_ato(self):
        resposta = self.salvar(0, area='0.012')

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(str(lancamento.area), '0.0120')
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_descarte_explicito_salva_sem_area_e_importa_o_ato(self):
        resposta = self.salvar(0, area='', descartar_area='1')

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertIsNone(lancamento.area)
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.status_revisao, 'importado')
        self.assertFalse(campo.area_convertida)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_sem_area_nem_descarte_volta_com_erro_e_nao_grava(self):
        antes = self.contagens()

        resposta = self.salvar(0, area='')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists(),
        )
        self.assertFalse(ImportacaoIA.objects.filter(ocr_job=self.job).exists())
        self.assertIn(
            '12,5 alqueires no documento',
            ' '.join(self.mensagens(resposta)),
        )
        html = resposta.content.decode()
        self.assertRegex(
            html,
            r'name="descartar_area"[^>]*form="lancamento-form"',
        )
        self.assertIn('Área lida em alqueires, descartada pelo revisor.', html)
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.status_revisao, 'sugerido')
        self.assertFalse(campo.area_convertida)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')


class DuplicataTest(RevisaoFormularioBase):
    def test_salvar_duas_vezes_grava_um_lancamento_so(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)

        self.client.post(self.url_ato(0), post)
        segunda = self.client.post(self.url_ato(0), post)

        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 1)
        self.assertEqual(ImportacaoIA.objects.filter(modelo='Lancamento').count(), 1)
        self.assertIn(
            'Este ato já foi salvo como lançamento. Nada foi gravado de novo.',
            self.mensagens(segunda),
        )

    def test_numero_repetido_e_barrado_pelo_service_do_formulario(self):
        # Lançamento criado fora da revisão com o MESMO número: quem recusa
        # é a regra do service manual, não uma checagem nova da revisão.
        Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R1 M237', data='2019-01-01',
        )
        antes = self.contagens()

        resposta = self.salvar(0, observacoes='o que eu digitei')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertTrue(any(
            'Já existe um lançamento com o número' in texto
            for texto in self.mensagens(resposta)
        ))
        html = resposta.content.decode()
        self.assertIn('data-numero-lancamento-error="true"', html)
        self.assertIn('o que eu digitei', html)
        self.assertIn('Revisão da extração · ato 1 de 3', html)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')

    def test_erro_do_service_preserva_a_digitacao_e_nao_grava(self):
        antes = self.contagens()

        resposta = self.salvar(
            0, tipo_lancamento='', observacoes='texto digitado',
            numero_lancamento_simples='7',
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertIn(
            'Tipo de lançamento é obrigatório',
            ' '.join(self.mensagens(resposta)),
        )
        html = resposta.content.decode()
        self.assertIn('texto digitado', html)
        self.assertRegex(html, r'name="numero_lancamento_simples"[^>]*value="7"')
        self.assertIn('JOÃO DA SILVA', html)

    def test_erro_interno_nao_vaza_e_nao_deixa_gravar_pela_metade(self):
        from unittest import mock

        antes = self.contagens()
        with mock.patch(
            'ia_ocr.revisao_ato.importacao._vincular', side_effect=RuntimeError('falhou'),
        ), self.assertLogs('ia_ocr.views', level='ERROR'):
            resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 200)
        # O lançamento criado antes da falha foi desfeito junto: nada de ato
        # "salvo" sem o vínculo da auditoria.
        self.assertEqual(self.contagens(), antes)
        self.assertNotIn('falhou', resposta.content.decode())
        self.assertIn('❌ Erro interno ao salvar o ato. Tente novamente.', self.mensagens(resposta))

    def test_duplicata_de_origem_nao_cria_nada_nem_perde_a_digitacao(self):
        from unittest import mock

        info = {'tipo': 'duplicata_encontrada', 'duplicata_info': {}}
        antes = self.contagens()
        with mock.patch(
            'ia_ocr.revisao_ato.LancamentoService.criar_lancamento_completo',
            return_value=(info, 'Origem já existe em outra cadeia.'),
        ):
            resposta = self.salvar(0, observacoes='digitado antes')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertIn('digitado antes', resposta.content.decode())
        self.assertTrue(any('já existe em outra cadeia' in t for t in self.mensagens(resposta)))

class RollbackDoErroInternoTest(RevisaoFormularioBase):
    """M4 (#341): depois do rollback, o livro/folha falsamente definidos somem."""

    def test_re_render_do_erro_interno_nao_trava_livro_que_o_banco_nao_tem(self):
        from unittest import mock

        pagina = self.client.get(self.url_ato(0))
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.livro, '')

        with mock.patch(
            'ia_ocr.revisao_ato.importacao._vincular', side_effect=RuntimeError('falhou'),
        ), self.assertLogs('ia_ocr.views', level='ERROR'):
            resposta = self.client.post(
                self.url_ato(0), post_do_html(pagina, livro_documento='99'),
            )

        self.assertEqual(resposta.status_code, 200)
        # O banco voltou ao estado anterior (rollback)…
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.livro, '')
        # …e a tela também: o input segue editável e com o que foi digitado,
        # não travado (disabled) com o '99' que só existia em memória.
        html = resposta.content.decode()
        entrada = re.search(r'<input[^>]*name="livro_documento"[^>]*>', html).group(0)
        self.assertNotIn('disabled', entrada)
        self.assertIn('value="99"', entrada)
