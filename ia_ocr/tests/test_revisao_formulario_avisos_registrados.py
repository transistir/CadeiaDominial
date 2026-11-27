"""#332: "importar e corrigir depois" — snapshot de avisos no vínculo."""

import json
from unittest import mock

from django.urls import reverse

from dominial.models import Lancamento, Pessoas
from ia_ocr.models import ImportacaoIA
from ia_ocr.revisao_ato.avisos_registrados import avisos_do_lancamento

from .payloads_extracao import payload_averbacao, payload_registro
from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, post_do_html,
)


class AvisosRegistradosTest(RevisaoFormularioBase):
    def _lancamento(self):
        return Lancamento.objects.get(documento=self.documento)

    def _snapshot(self):
        return ImportacaoIA.objects.get(
            modelo='Lancamento', objeto_id=self._lancamento().pk,
        ).avisos

    def _ultimo_com_area(self, area):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['area'] = {
            **self._campo('12.50', 'área 12,50 alqueires'),
            'unidade': 'alqueires', 'raw': '12,50 alqueires',
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        return area

    def test_snapshot_e_gravado_no_vinculo_do_lancamento(self):
        self.salvar(0)

        avisos = self._snapshot()
        self.assertTrue(avisos)
        self.assertIn('lido_sem_campo', [aviso['motivo'] for aviso in avisos])
        for aviso in avisos:
            self.assertEqual(set(aviso), {'motivo', 'rotulo', 'texto'})

    def test_snapshot_nao_tem_pii(self):
        self.salvar(0)

        serializado = json.dumps(self._snapshot(), ensure_ascii=False)

        for proibido in (
            '123.456.789-00', '987.654.321-00', '12345678900',
            '98765432100', 'JOÃO', 'MARIA', 'PEDRO',
        ):
            self.assertNotIn(proibido, serializado)

    def _com_forma_trocada_com_cpf(self):
        payload = payload_registro(self.job.job_id)
        ato = payload['acts'][0]
        ato['forma'] = self._campo(
            'Escritura Pública CPF 123.456.789-00', 'Escritura Pública',
        )
        ato['titulo'] = self._campo('Venda e Compra', 'Venda e Compra')
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_snapshot_usa_texto_controlado_sem_pii(self):
        self._com_forma_trocada_com_cpf()

        self.salvar(0)

        avisos = self._snapshot()
        aviso = next(
            item for item in avisos
            if item['motivo'] == 'forma_titulo_reinterpretados'
        )
        self.assertEqual(
            aviso['texto'],
            'Forma e título foram reinterpretados; confira os dois campos.',
        )
        serializado = json.dumps(avisos, ensure_ascii=False)
        for proibido in ('123.456.789-00', '12345678900'):
            self.assertNotIn(proibido, serializado)

    def _registro_sem_forma_que_requer_forma(self):
        self.tipo_registro.requer_forma = True
        self.tipo_registro.save(update_fields=['requer_forma'])
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload_registro(self.job.job_id))

    def test_requer_forma_some_quando_o_post_preenche_a_forma(self):
        self._registro_sem_forma_que_requer_forma()

        self.salvar(0, forma_transacao='Compra e venda')

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertNotIn('requer_forma', motivos)
        self.assertEqual(self._lancamento().forma, 'Compra e venda')

    def test_requer_forma_fica_quando_so_forma_averbacao_no_registro(self):
        self._registro_sem_forma_que_requer_forma()

        self.salvar(0, forma_averbacao='Compra e venda', forma_transacao='')

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertIn('requer_forma', motivos)
        self.assertIsNone(self._lancamento().forma)

    def test_snapshot_guarda_todos_os_lidos_sem_campo(self):
        self.salvar(0)

        rotulos = [
            aviso['rotulo'] for aviso in self._snapshot()
            if aviso['motivo'] == 'lido_sem_campo'
        ]
        self.assertIn('CPF/RG das partes', rotulos)
        self.assertIn('Valor da transação', rotulos)

    def test_requer_transmissao_some_com_lista_que_tem_linha_vazia(self):
        self.tipo_registro.requer_transmissao = True
        self.tipo_registro.save(update_fields=['requer_transmissao'])
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'] = payload['acts'][0]['partes'][2:]
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        pessoa = Pessoas.objects.create(nome='FULANO DE TAL')

        self.salvar(0, **{
            'transmitente[]': [str(pessoa.pk), ''],
            'transmitente_nome[]': ['FULANO DE TAL', ''],
            'adquirente[]': [str(pessoa.pk), ''],
            'adquirente_nome[]': ['FULANO DE TAL', ''],
        })

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertNotIn('requer_transmissao', motivos)

    def test_requer_forma_fica_quando_o_post_nao_preenche(self):
        self._registro_sem_forma_que_requer_forma()

        self.salvar(0)

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertIn('requer_forma', motivos)

    def test_requer_observacao_some_com_observacoes_no_post(self):
        payload = payload_averbacao(self.job.job_id)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        self.salvar(0, observacoes='x')

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertNotIn('requer_observacao', motivos)

    def test_area_salva_nao_registra_area_descartada(self):
        self._ultimo_com_area(None)

        self.salvar(0, area='0.012', descartar_area='1')

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertNotIn('area_descartada', motivos)

    def test_bloqueante_resolvido_nao_vira_aviso(self):
        self._ultimo_com_area('0.0120')

        self.salvar(0, area='0.012')

        motivos = [aviso['motivo'] for aviso in self._snapshot()]
        self.assertNotIn('unidade_area', motivos)

    def test_descarte_vira_area_descartada(self):
        self._ultimo_com_area(None)

        resposta = self.salvar(0, area='', descartar_area='1')

        self.assertEqual(resposta.status_code, 302)
        avisos = self._snapshot()
        descartes = [
            aviso for aviso in avisos if aviso['motivo'] == 'area_descartada'
        ]
        self.assertEqual(len(descartes), 1)
        self.assertIn('descartada pelo revisor', descartes[0]['texto'])
        self.assertNotIn('unidade_area', [aviso['motivo'] for aviso in avisos])

    def test_edicao_do_lancamento_mostra_o_painel(self):
        self.salvar(0)
        lancamento = self._lancamento()

        resposta = self.client.get(reverse('editar_lancamento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'lancamento_id': lancamento.pk,
        }))

        html = resposta.content.decode()
        self.assertIn('ia-avisos-importacao', html)
        self.assertIn('CPF/RG das partes', html)

    def test_lancamento_manual_nao_mostra_o_painel(self):
        resposta = self.client.get(reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        }))

        self.assertNotIn('ia-avisos-importacao', resposta.content.decode())

    def test_avisos_sobrevivem_a_exclusao_do_pdf(self):
        self.salvar(0)
        lancamento = self._lancamento()
        antes = avisos_do_lancamento(lancamento)
        self.assertTrue(antes)

        self.job.delete()
        self.arquivo.delete()

        self.assertEqual(avisos_do_lancamento(lancamento), antes)

    def test_mensagem_pos_save_com_avisos(self):
        resposta = self.salvar(0)

        mensagens = ' '.join(self.mensagens(resposta))
        self.assertIn('O ato R1 foi salvo com', mensagens)
        self.assertIn('aviso(s) para conferir depois', mensagens)

    def test_mensagem_pos_save_sem_avisos(self):
        self.tipo_averbacao.requer_observacao = False
        self.tipo_averbacao.save(update_fields=['requer_observacao'])
        payload = payload_averbacao(self.job.job_id)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        resposta = self.salvar(0)

        self.assertEqual(self._snapshot(), [])
        self.assertNotIn(
            'aviso(s) para conferir depois', ' '.join(self.mensagens(resposta)),
        )

    def test_caminho_da_duplicata_tambem_registra(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)

        with mock.patch(
            'ia_ocr.views.revisar_extras.'
            'LancamentoDuplicataService.processar_importacao_duplicata',
            return_value={
                'sucesso': True, 'documentos_importados': 0, 'erros': [],
            },
        ):
            resposta = self.client.post(self.url_ato(0) + 'duplicata/', post)

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(self._snapshot())
