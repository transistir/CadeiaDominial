"""``PartesTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
import json

from dominial.models import Pessoas
from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import payload_registro

class PartesTestParte:
    def test_partes_no_formato_do_pessoa_form(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        self.assertEqual(resultado['transmitentes'], [
            {'id': '', 'nome': 'JOÃO DA SILVA'},
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertEqual(resultado['adquirentes'], [
            {'id': '', 'nome': 'PEDRO SANTOS'},
        ])

    def test_pessoa_escolhida_leva_id_e_nome_do_cadastro(self):
        pessoa = Pessoas.objects.create(nome='João da Silva (cadastro)')
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            pessoa_escolhida=pessoa,
        )
        extracao.campos.filter(chave='/acts/0/partes/1').update(criar_novo=True)

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['transmitentes'], [
            {'id': str(pessoa.pk), 'nome': 'João da Silva (cadastro)'},
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertFalse(Pessoas.objects.filter(nome='MARIA DA SILVA').exists())

    def test_conjuge_e_parte_descartada_ficam_de_fora(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            valor_final='conjuge', status_revisao='editado',
        )
        extracao.campos.filter(chave='/acts/0/partes/2').update(
            status_revisao='descartado',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['transmitentes'], [
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertEqual(resultado['adquirentes'], [])

    def test_cpf_e_rg_nao_aparecem_em_lugar_nenhum(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        serializado = json.dumps(resultado, ensure_ascii=False, default=str)
        for sensivel in ('123.456.789-00', '12345678900', '987.654.321-00'):
            self.assertNotIn(sensivel, serializado)
