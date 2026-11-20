"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from copy import deepcopy
from datetime import date
from dominial.models import (
    Cartorios, Lancamento,
    LancamentoTipo, Pessoas,
)
from ia_ocr.importacao import ImportacaoInvalida
from ia_ocr.models import ImportacaoIA, OcrJob
from .payloads_extracao import (
    payload_registro,
)
from .test_importacao_base import ImportacaoBase


class DuplicidadeTest(ImportacaoBase):
    """Cenário 4: as três formas de cair no lançamento já existente."""

    def setUp(self):
        super().setUp()
        self.extracao = self._extracao(self._payload_com_numero())

    def _existente(self, numero, tipo=None, data=None):
        return Lancamento.objects.create(
            documento=self.documento,
            tipo=tipo or self.tipo_registro,
            numero_lancamento=numero,
            data=data or date(2020, 2, 15),
        )

    def _erros(self):
        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(self.extracao)
        return contexto.exception.linhas[0]['erros']

    def test_mesma_tupla_documento_tipo_data_numero(self):
        existente = self._existente('R-1')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['chave'], '/acts/0')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(
            erro['existente']['url'], self.url_lancamento(existente),
        )
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_mesmo_numero_com_tipo_e_data_diferentes(self):
        tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        existente = self._existente(
            'R-1', tipo=tipo_averbacao, data=date(2021, 1, 1),
        )

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)

    def test_numero_nulo_casa_com_existente_sem_numero(self):
        # Uma extração finalizada por job (constraint): o mesmo documento
        # ganha um SEGUNDO job revisado para o payload sem número.
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        extracao = self._extracao(payload_registro(self.job.job_id))
        self._existente(None)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')

    def test_numero_com_espacos_casa_com_o_normalizado(self):
        # Rodada 6 (Codex P2): o número comparado é o strip, como o fluxo
        # manual valida — ' R-1 ' é duplicata de 'R-1', não lançamento novo.
        self._novo_job_com_extracao(' R-1 ')
        existente = self._existente('R-1')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_numero_da_gravacao_e_strip(self):
        # #322 rodada 3 (P1-1): o valor PERSISTIDO é o composto canônico do
        # V1 — ' R-1 ' grava 'R1 {sigla}', nunca o carimbo inteiro; as
        # bordas seguem removidas (rodada 6).
        self._novo_job_com_extracao(' R-1 ')

        resultado = self._importar(self.extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(
            Lancamento.objects.get().numero_lancamento,
            f'R1 {self.documento.numero}',
        )

    def test_numero_somente_espacos_grava_none(self):
        # Rodada 8 (review Opus, P3): '   ' virava '' gravado — lixo que o
        # fluxo manual nunca grava (ele guarda None). ``(strip) or None``
        # alinha os dois fluxos.
        self._novo_job_com_extracao('   ')

        resultado = self._importar(self.extracao)

        self.assertTrue(resultado['ok'])
        self.assertIsNone(Lancamento.objects.get().numero_lancamento)

    def test_gravado_com_bordas_recusa_o_importado_sem_bordas(self):
        # Rodada 7 (review Codex): a rodada 6 normalizou só o número
        # RECEBIDO. Quem já tem ' R-1 ' gravado (importador anterior e
        # edição manual gravam bordas) não pode receber 'R-1' como novo.
        existente = self._existente(' R-1 ')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_gravado_com_newline_recusa_o_importado_sem_bordas(self):
        # Rodada 8 (review Opus, P2): o lado GRAVADO era normalizado por
        # TRIM() do SQL, que só tira espaço — o '\n' que texto de OCR deixa
        # no fim do número escapava da duplicata. Os dois lados passam a
        # usar a MESMA normalização (o .strip() do Python, o que grava).
        existente = self._existente('R-1\n')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_gravado_com_newline_e_espacos_recusa_o_importado(self):
        # 'R-1 \n ' gravado x ' R-1 ' recebido: a borda mista sobrava '\n'
        # depois do TRIM e casava com o recebido normalizado ('R-1') — o
        # ato passava como lançamento novo.
        self._novo_job_com_extracao(' R-1 ')
        existente = self._existente('R-1 \n ')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_segundo_filtro_normaliza_o_numero_gravado(self):
        # O fallback "número sozinho dentro do documento, mudando tipo/data"
        # compara o gravado sem bordas do mesmo jeito.
        tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        existente = self._existente(
            ' R-1 ', tipo=tipo_averbacao, data=date(2021, 1, 1),
        )

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_gravado_somente_espacos_cai_no_ramo_de_vazio(self):
        # Gravado só com espaços é vazio: o ato sem número casa no ramo de
        # null/'' da dupla (documento, tipo, data), como um '' gravado.
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        extracao = self._extracao(payload_registro(self.job.job_id))
        existente = self._existente('   ')

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)

    def _novo_job_com_extracao(self, numero):
        """Extracao finalizada nova (constraint: uma por job), número dado."""
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        payload = self._payload_com_numero()
        payload['acts'][0]['numero_lancamento'] = self._campo(
            numero, 'R-1/42.718',
        )
        self.extracao = self._extracao(payload)

    def _payload_com_numero_com_espacos(self, numero):
        payload = self._payload_com_numero()
        payload['acts'][0]['numero_lancamento'] = self._campo(
            numero, 'R-1/42.718',
        )
        return payload


class DuplicataInternaTest(ImportacaoBase):
    """B3 (#263 rodada 3): dois atos do payload com o mesmo lançamento.

    O ato 1 grava no savepoint dele; o ato 2 colide com ELE, que o
    rollback global vai desfazer. ``existente`` só aponta registro anterior
    à importação — a colisão interna é erro na chave do ato conflitante.
    """

    def test_dois_atos_iguais_recusam_sem_existente(self):
        payload = self._payload_com_numero()
        payload['acts'].append(deepcopy(payload['acts'][0]) | {'ordem': 2})
        extracao = self._extracao(payload)
        antes = (
            Pessoas.objects.count(), Cartorios.objects.count(),
            ImportacaoIA.objects.count(),
        )

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        primeiro, segundo = contexto.exception.linhas
        self.assertEqual(primeiro['chave'], '/acts/0')
        self.assertEqual(primeiro['status'], 'nao_gravado')
        self.assertIsNone(primeiro['lancamento_id'])
        self.assertEqual(segundo['chave'], '/acts/1')
        self.assertEqual(segundo['status'], 'erro')
        (erro,) = segundo['erros']
        self.assertEqual(erro['chave'], '/acts/1')
        self.assertEqual(erro['codigo'], 'ato_duplicado_na_importacao')
        self.assertNotIn('existente', erro)
        # Nada gravado: nem o ato 1, nem pessoas/cartórios/vínculos.
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(
            (
                Pessoas.objects.count(), Cartorios.objects.count(),
                ImportacaoIA.objects.count(),
            ),
            antes,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')

    def test_registro_anterior_continua_com_existente(self):
        # A colisão com o que já existia antes da importação segue com o
        # ``existente`` — mesmo quando um ato anterior também gravou.
        existente = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R-2', data=date(2021, 3, 20),
        )
        payload = self._payload_com_numero()
        segundo = deepcopy(payload['acts'][0]) | {'ordem': 2}
        segundo['numero_lancamento'] = self._campo('R-2', 'R-1/42.718')
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[1]['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)
