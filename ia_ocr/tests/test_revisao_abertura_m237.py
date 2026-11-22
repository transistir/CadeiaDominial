"""Abertura de matrícula (A3 do ocr-service #75) no formulário da revisão.

A matrícula M237/Itamaraju (caso público #72, redigido) nasce de uma
transcrição: o serviço passou a emitir o PRIMEIRO ato como
``inicio_matricula`` (``M-237``), e estes testes provam que o app já o
mapeia sem campo, template ou migration novos — rota própria continua
sendo o formulário de lançamento (I-14 / #341).
"""

import re

from dominial.models import Documento, Lancamento
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from ia_ocr import revisao_ato
from ia_ocr.extracao_schema import validar_payload
from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import TEXTO_M237, payload_m237_abertura
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class AberturaM237Base(RevisaoFormularioBase):
    """Job em ``extraido`` com a M237 inteira: abertura + 7 R/Av."""

    def setUp(self):
        super().setUp()
        # A base abre três atos sobre o texto sintético curto; a evidência
        # da M237 precisa do texto próprio e o composto do início de
        # matrícula usa o número do documento ("237", não "M237").
        self.extracao.delete()
        self.pagina.texto_ocr = TEXTO_M237
        self.pagina.save(update_fields=['texto_ocr'])
        Documento.objects.filter(pk=self.documento.pk).update(numero='237')
        self.documento.refresh_from_db()
        self.extracao = self._aberta(payload_m237_abertura(self.job.job_id))

    def _abas_da_sidebar(self, html):
        sidebar = html[html.index('ia-revisao-sidebar'):]
        return re.findall(
            r'>(\d+)\. (R\d+|Av\d+|Abertura)',
            sidebar[:sidebar.index('</aside>')],
        )


class PayloadM237Test(AberturaM237Base):
    def test_payload_m237_valida_no_contrato_v12(self):
        payload = payload_m237_abertura(self.job.job_id)

        validar_payload(payload, self.job.job_id, [1])

        # Fixture íntegra: toda evidência é literal no texto OCR sintético
        # (a mesma checagem que a desnormalização faz trecho a trecho).
        for trecho in self._trechos(payload):
            self.assertIn(trecho, TEXTO_M237)

    @staticmethod
    def _trechos(no):
        if isinstance(no, dict):
            for chave, valor in no.items():
                if chave == 'evidencia' and isinstance(valor, dict):
                    yield valor['trecho']
                else:
                    yield from PayloadM237Test._trechos(valor)
        elif isinstance(no, list):
            for item in no:
                yield from PayloadM237Test._trechos(item)


class AberturaNaRevisaoTest(AberturaM237Base):
    def test_abertura_aparece_como_inicio_matricula(self):
        atos = revisao_ato.atos_da_revisao(self.extracao)

        self.assertEqual(len(atos), 8)
        self.assertTrue(atos[0]['eh_inicio'])
        self.assertFalse(any(ato['eh_inicio'] for ato in atos[1:]))
        self.assertEqual(atos[0]['rotulo'], 'Abertura')

    def test_ordem_dos_atos_preservada(self):
        atos = revisao_ato.atos_da_revisao(self.extracao)

        self.assertEqual(
            [(ato['indice'], ato['posicao'], ato['rotulo']) for ato in atos],
            [
                (0, 1, 'Abertura'), (1, 2, 'R1'), (2, 3, 'Av2'),
                (3, 4, 'Av3'), (4, 5, 'R4'), (5, 6, 'R5'),
                (6, 7, 'Av6'), (7, 8, 'Av7'),
            ],
        )

    def test_abertura_por_ultimo_na_sidebar(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        # Chave da view: (eh_inicio, -posicao) — os R/Av seguem do maior
        # ato para o menor e a abertura fica SEMPRE por último.
        self.assertEqual(
            self._abas_da_sidebar(html),
            [
                ('8', 'Av7'), ('7', 'Av6'), ('6', 'R5'), ('5', 'R4'),
                ('4', 'Av3'), ('3', 'Av2'), ('2', 'R1'), ('1', 'Abertura'),
            ],
        )


class PrefillDaAberturaTest(AberturaM237Base):
    def test_prefill_da_abertura(self):
        form_data = prefill_do_ato(
            self.extracao, 0, self.documento,
        )['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_inicio.pk))
        self.assertEqual(form_data['data'], '1982-06-09')
        self.assertEqual(form_data['area'], '169.0940')
        self.assertEqual(form_data['livro_documento'], '2')
        self.assertEqual(form_data['folha_documento'], '237')

    def test_numero_da_matricula_nao_vira_numero_de_ato(self):
        form_data = prefill_do_ato(
            self.extracao, 0, self.documento,
        )['form_data']

        simples = form_data.get('numero_lancamento_simples', '')
        self.assertNotIn('M-237', simples)
        self.assertNotIn('M237', simples)
        # Início de matrícula: o composto é a sigla da matrícula, como no
        # formulário manual de início.
        self.assertEqual(form_data['numero_lancamento'], '237')

    def test_area_do_documento_sem_area_no_ato_nao_inventa(self):
        payload = payload_m237_abertura(self.job.job_id)
        self.assertEqual(payload['document']['area']['normalized'], '169.0940')
        payload['acts'][0].pop('area')

        resultado = prefill_do_ato(
            self._aberta(payload), 0, self.documento,
        )

        # Sem inferência: a área do cabeçalho não preenche o ato — a
        # associação precisa estar no ato, com evidência própria.
        self.assertNotIn('area', resultado['form_data'])

    def test_livro_folha_da_origem_nao_se_misturam(self):
        resultado = prefill_do_ato(self.extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['livro_documento'], '2')
        self.assertEqual(resultado['form_data']['folha_documento'], '237')
        (origem,) = resultado['origens_separadas']
        self.assertEqual(origem['livro'], '3')
        self.assertEqual(origem['folha'], '12')
        self.assertEqual(origem['texto'], 'T4321')


class SemAberturaTest(AberturaM237Base):
    def test_r_av_continuam_iguais_sem_abertura(self):
        payload = payload_m237_abertura(self.job.job_id)
        payload['acts'].pop(0)
        for ordem, ato in enumerate(payload['acts'], start=1):
            ato['ordem'] = ordem

        atos = revisao_ato.atos_da_revisao(self._aberta(payload))

        self.assertEqual(len(atos), 7)
        self.assertFalse(any(ato['eh_inicio'] for ato in atos))
        self.assertEqual(
            [ato['rotulo'] for ato in atos],
            ['R1', 'Av2', 'Av3', 'R4', 'R5', 'Av6', 'Av7'],
        )
        self.assertEqual(
            [ato['posicao'] for ato in atos], [1, 2, 3, 4, 5, 6, 7],
        )


class SalvarAberturaEhInicioMatriculaTest(AberturaM237Base):
    def test_salvar_abertura_grava_eh_inicio_matricula_true(self):
        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertTrue(lancamento.eh_inicio_matricula)

    def test_salvar_r_ou_av_grava_eh_inicio_matricula_false(self):
        self.salvar(0)

        resposta = self.salvar(1)

        self.assertEqual(resposta.status_code, 302)
        lancamentos = Lancamento.objects.filter(documento=self.documento).order_by('id')
        self.assertEqual(lancamentos.count(), 2)
        self.assertTrue(lancamentos[0].eh_inicio_matricula)
        self.assertFalse(lancamentos[1].eh_inicio_matricula)

    def test_criacao_manual_inicio_matricula_grava_true_e_registro_false(self):
        dados_inicio = {
            'tipo_lancamento': str(self.tipo_inicio.pk),
            'numero_lancamento': '1',
            'data': '2020-01-01',
            'observacoes': '',
            'forma': '',
            'descricao': '',
            'titulo': '',
            'livro_origem': '',
            'folha_origem': '',
            'cartorio_origem': None,
            'area': None,
            'origem': '',
        }
        manual_inicio = LancamentoCriacaoService._criar_lancamento_basico(
            self.documento, dados_inicio, self.tipo_inicio,
        )
        self.assertTrue(manual_inicio.eh_inicio_matricula)

        dados_reg = dict(dados_inicio, numero_lancamento='2')
        manual_reg = LancamentoCriacaoService._criar_lancamento_basico(
            self.documento, dados_reg, self.tipo_registro,
        )
        self.assertFalse(manual_reg.eh_inicio_matricula)
