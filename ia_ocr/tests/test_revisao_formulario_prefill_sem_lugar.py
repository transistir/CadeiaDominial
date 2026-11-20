"""``SemLugarNoFormularioTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
import json

from ia_ocr.formulario import TEXTO_LIDO_SEM_CAMPO, prefill_do_ato
from ia_ocr.models import CampoSugerido

from .payloads_extracao import payload_averbacao

class SemLugarNoFormularioTestParte:
    def _rotulos(self, resultado):
        return [aviso['rotulo'] for aviso in resultado['pendencias']]

    def test_campos_lidos_sem_lugar_viram_aviso_informativo(self):
        payload = self._registro(
            detalhes=self._campo('Detalhes do ato', 'Escritura Pública'),
        )
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'data': self._campo('1990-01-02', '10 de janeiro de 2020'),
        }

        resultado = self._prefill(payload)

        self.assertEqual(self._rotulos(resultado), [
            'Data da origem', 'CPF/RG das partes', 'Valor da transação',
            'Detalhes',
        ])
        for aviso in resultado['pendencias']:
            with self.subTest(rotulo=aviso['rotulo']):
                self.assertFalse(aviso['bloqueante'])
                self.assertEqual(aviso['texto'], TEXTO_LIDO_SEM_CAMPO)
                self.assertEqual(aviso['texto'], 'lido, sem campo no lançamento')

    def test_nada_disso_entra_no_form_data_nem_cita_a_chave(self):
        payload = self._registro(
            detalhes=self._campo('Detalhes do ato', 'Escritura Pública'),
        )
        payload['acts'][0]['origem'] = {
            'numero': self._campo('T366', '42.718'),
            'data': self._campo('1990-01-02', '10 de janeiro de 2020'),
        }

        resultado = self._prefill(payload)

        valores = ' '.join(resultado['form_data'].values())
        for lido in ('150000', 'Detalhes do ato', '1990-01-02', '12345678900'):
            self.assertNotIn(lido, valores)
        for nome in resultado['form_data']:
            self.assertNotIn('valor', nome)
            self.assertNotIn('detalhes', nome)
        for aviso in resultado['pendencias']:
            self.assertNotIn('/acts/', json.dumps(aviso, ensure_ascii=False))

    def test_valor_e_detalhes_de_linha_antiga_tambem_avisam(self):
        # Extração salva antes do #328: a linha existe, é ignorada na
        # leitura, e o payload segue com o valor lido.
        payload = self._registro()
        extracao = self._aberta(payload)
        CampoSugerido.objects.create(
            extracao=extracao, chave='/acts/0/valor_transacao',
            raw='150000.00', normalized='150000.00', tipo_valor='texto',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertIn('Valor da transação', self._rotulos(resultado))

    def test_sem_nada_lido_sem_lugar_nao_ha_aviso(self):
        resultado = self._prefill(payload_averbacao(self.job.job_id))

        self.assertEqual(resultado['pendencias'], [])

    def test_folha_vazia_nao_gera_aviso(self):
        resultado = self._prefill(self._averbacao(
            valor_transacao={
                'raw': None, 'normalized': None, 'confianca': 0.9,
                'requer_revisao': False,
            },
        ))

        self.assertEqual(resultado['pendencias'], [])
