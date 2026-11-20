"""``ContratoDaFuncaoTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
from copy import deepcopy

from django.db import connection
from django.test.utils import CaptureQueriesContext

from dominial.models import Cartorios, Pessoas
from ia_ocr.formulario import AtoInexistente, prefill_do_ato
from ia_ocr.models import CampoSugerido

from .payloads_extracao import payload_averbacao, payload_registro

class ContratoDaFuncaoTestParte:
    def test_devolve_as_seis_chaves(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        self.assertEqual(set(resultado), {
            'form_data', 'origens_separadas', 'transmitentes', 'adquirentes',
            'evidencias', 'pendencias',
        })

    def test_funciona_com_job_extraido_e_nada_finalizado(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        self.assertEqual(self.job.status, 'extraido')
        self.assertIsNone(extracao.finalizada_em)

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['data'], '2020-02-15')

    def test_cada_ato_pelo_proprio_indice(self):
        payload = payload_registro(self.job.job_id)
        segundo = payload_averbacao(self.job.job_id)['acts'][0]
        segundo['ordem'] = 2
        payload['acts'].append(segundo)
        extracao = self._aberta(payload)

        primeiro = prefill_do_ato(extracao, 0, self.documento)['form_data']
        outro = prefill_do_ato(extracao, 1, self.documento)['form_data']

        self.assertEqual(primeiro['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(primeiro['data'], '2020-02-15')
        self.assertEqual(outro['tipo_lancamento'], str(self.tipo_averbacao.pk))
        self.assertEqual(outro['data'], '2021-03-20')
        self.assertEqual(outro['descricao'], 'averbação de construção de casa sede')

    def test_indice_inexistente_ou_ato_descartado(self):
        extracao = self._aberta(payload_registro(self.job.job_id))

        with self.assertRaises(AtoInexistente):
            prefill_do_ato(extracao, 5, self.documento)

        extracao.campos.filter(chave='/acts/0').update(status_revisao='descartado')
        with self.assertRaises(AtoInexistente):
            prefill_do_ato(extracao, 0, self.documento)

    def test_consultas_nao_crescem_com_o_numero_de_partes(self):
        def consultas(quantas):
            payload = payload_registro(self.job.job_id)
            parte = payload['acts'][0]['partes'][2]
            payload['acts'][0]['partes'] = [deepcopy(parte) for _ in range(quantas)]
            extracao = self._aberta(payload)
            for posicao in range(quantas):
                pessoa = Pessoas.objects.create(nome='Pessoa %d' % posicao)
                extracao.campos.filter(
                    chave='/acts/0/partes/%d' % posicao,
                ).update(pessoa_escolhida=pessoa)
            with CaptureQueriesContext(connection) as capturadas:
                resultado = prefill_do_ato(extracao, 0, self.documento)
            self.assertEqual(len(resultado['adquirentes']), quantas)
            extracao.delete()
            return len(capturadas)

        self.assertEqual(consultas(1), consultas(8))

    def test_nao_escreve_nada(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        antes = (
            CampoSugerido.objects.count(), Pessoas.objects.count(),
            Cartorios.objects.count(),
        )

        with CaptureQueriesContext(connection) as capturadas:
            prefill_do_ato(extracao, 0, self.documento)

        escritas = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]
        self.assertEqual(escritas, [])
        self.assertEqual(antes, (
            CampoSugerido.objects.count(), Pessoas.objects.count(),
            Cartorios.objects.count(),
        ))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')
