"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from datetime import date
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.utils import timezone
from dominial.models import (
    Documento, DocumentoTipo, Lancamento,
    LancamentoTipo, Pessoas,
)
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from ia_ocr.importacao import ImportacaoInvalida, resumo
from ia_ocr.models import CampoSugerido, ImportacaoIA
from .factories import criar_usuario
from .payloads_extracao import (
    payload_averbacao, payload_registro,
)
from .test_importacao_base import ImportacaoBase


class ResumoTest(ImportacaoBase):
    def test_resumo_aponta_duplicado_sem_gravar(self):
        extracao = self._extracao(self._payload_com_numero())
        existente = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R-1', data=date(2020, 2, 15),
        )

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertEqual(ato['chave'], '/acts/0')
        self.assertEqual(ato['rotulo'], 'R-1')
        self.assertTrue(ato['duplicado'])
        self.assertEqual(ato['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(self.job.status, 'revisado')

    def test_resumo_sem_duplicado(self):
        extracao = self._extracao(self._payload_com_numero())

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertFalse(ato['duplicado'])
        self.assertIsNone(ato['existente'])

    def test_resumo_normaliza_o_numero_gravado(self):
        # Rodada 7: a pendência da prévia herda a comparação dos dois lados
        # normalizados — ' R-1 ' gravado marca a importação de 'R-1'.
        extracao = self._extracao(self._payload_com_numero())
        existente = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento=' R-1 ', data=date(2020, 2, 15),
        )

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertTrue(ato['duplicado'])
        self.assertEqual(ato['existente']['id'], existente.pk)


# ---------------------------------------------------------------------------
# Rodada 2 (review Codex #263): corrida IA × manual, cache de pessoas,
# savepoint por ato, origem longa, linhas descartadas, auditoria do
# documento de origem, erro de pessoa ancorado na parte e stdout sem
# valor documental.
# ---------------------------------------------------------------------------


class SavepointPorAtoTest(ImportacaoBase):
    """P2-3 (#263 rodada 2): o erro de um ato desfaz o savepoint DELE.

    Sem o rollback imediato, o que o ato inválido gravou fica de pé para
    os atos seguintes — que veem duplicata com um ``existente`` apontando
    para um registro que o rollback global vai desfazer.
    """

    def setUp(self):
        super().setUp()
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')

    def test_ato_invalido_desfaz_o_proprio_savepoint(self):
        payload = self._payload_com_numero()  # registro R-1 com partes
        averbacao = payload_averbacao(self.job.job_id)['acts'][0] | {'ordem': 2}
        averbacao['numero_lancamento'] = self._campo('R-1', 'Av-1/42.718')
        averbacao['partes'] = [{
            'papel': 'adquirente',
            'nome': {
                'raw': 'JOÃO DA SILVA', 'normalized': 'JOÃO DA SILVA',
                'confianca': 0.92, 'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
            },
            'documento_identificacao': {
                'tipo': {
                    'raw': 'CPF', 'normalized': 'CPF', 'confianca': 0.92,
                    'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
                },
                'valor': {
                    'raw': '123.456.789-00', 'normalized': '12345678900',
                    'confianca': 0.92, 'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
                },
            },
            'confianca': 0.92,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
        }]
        payload['acts'].append(averbacao)
        extracao = self._extracao(payload)
        pessoas_antes = Pessoas.objects.count()  # o factory já cria 1

        # Ato 1: grava o R-1 e a pessoa da 1ª parte (cacheada), e morre na
        # pessoa da 2ª. O savepoint tem que desfazer lançamento E cache —
        # senão o ato 2 vê duplicata (e reutilizaria pessoa desfeita).
        chamadas = iter(['ok', 'falha', 'ok'])

        def full_clean_pessoas():
            if next(chamadas) == 'falha':
                raise ValidationError({'cpf': ['Fora do limite.']})

        with patch.object(
            Pessoas, 'full_clean', side_effect=full_clean_pessoas,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        linhas = contexto.exception.linhas
        self.assertEqual(linhas[0]['chave'], '/acts/0')
        self.assertEqual(linhas[0]['status'], 'erro')
        self.assertEqual(linhas[1]['chave'], '/acts/1')
        # O ato 2 GRAVOU de verdade (o R-1 do ato 1 voltou ao nada com o
        # savepoint) e só foi desfeito pelo rollback global da recusa.
        self.assertEqual(linhas[1]['status'], 'nao_gravado')
        self.assertNotIn('erros', linhas[1])
        # Nenhum `existente` aponta para registro desfeito pelo rollback.
        for linha in linhas:
            for erro in linha.get('erros', []):
                if 'existente' in erro:
                    self.assertTrue(
                        Lancamento.objects
                        .filter(pk=erro['existente']['id']).exists(),
                    )
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Pessoas.objects.count(), pessoas_antes)
        # O ato 2 recriou o JOÃO: a entrada de cache do ato desfeito foi
        # descartada. Reaproveitada, ``full_clean`` rodaria só 2 vezes.
        self.assertIsNone(next(chamadas, None))


class OrigemLongaTest(ImportacaoBase):
    """P2-4 (#263 rodada 2): origem acima do limite vira 422, não 500."""

    def test_origem_com_50_digitos_e_erro_na_linha_da_origem(self):
        payload = self._payload_origem()
        payload['acts'][0]['origem']['numero'] = self._campo(
            '1' * 50, '42.718',
        )
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/numero')
        self.assertEqual(erro['codigo'], 'valor_acima_do_limite_destino')
        self.assertEqual(Lancamento.objects.count(), 0)


class LinhasDescartadasTest(ImportacaoBase):
    """P2-5 (#263 rodada 2): linha descartada não vira importada."""

    def test_parte_descartada_mantem_status_e_autoria_da_revisao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        outro = criar_usuario()
        # A revisão aceitou o nome do PEDRO e depois descartou SÓ a parte
        # (a linha-pai): a filha fica fora pelo ancestral, não por status
        # próprio (#263 rodada 3 — descartar pai e filhos não provava isso).
        CampoSugerido.objects.filter(chave='/acts/0/partes/2/nome').update(
            status_revisao='aceito',
            revisado_por=outro,
            revisado_em=timezone.now(),
        )
        CampoSugerido.objects.filter(chave='/acts/0/partes/2').update(
            status_revisao='descartado',
            revisado_por=outro,
            revisado_em=timezone.now(),
        )

        self._importar(extracao)

        # A parte descartada e a linha filha continuam como a revisão
        # deixou: a importação não reescreve decisão de descarte.
        pai = extracao.campos.get(chave='/acts/0/partes/2')
        self.assertEqual(pai.status_revisao, 'descartado')
        self.assertEqual(pai.revisado_por, outro)
        filha = extracao.campos.get(chave='/acts/0/partes/2/nome')
        self.assertEqual(filha.status_revisao, 'aceito')
        self.assertEqual(filha.revisado_por, outro)
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.pessoas.count(), 2)  # sem o PEDRO
        # As linhas incluídas do ato foram marcadas com o autor da importação.
        # Todas as demais linhas do ato foram marcadas com o autor da
        # importação.
        demais = (
            extracao.campos.filter(chave__startswith='/acts/0')
            .exclude(chave__startswith='/acts/0/partes/2')
        )
        self.assertTrue(demais.exists())
        self.assertFalse(
            demais.exclude(
                status_revisao='importado', revisado_por=self.usuario,
            ).exists()
        )


class DocumentoOrigemAuditadoTest(ImportacaoBase):
    """P2-6 (#263 rodada 2): documento de origem também gera ImportacaoIA."""

    def test_inicio_de_matricula_gera_vinculo_do_documento_criado(self):
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        # Rótulo de MATRÍCULA: com o rótulo prevalecendo (#322 rodada 3),
        # o 'R-1' do payload-base faria o ato virar registro.
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        extracao = self._extracao(payload)

        self._importar(extracao)

        lancamento = Lancamento.objects.get()
        (documento_origem,) = Documento.objects.exclude(pk=self.documento.pk)
        vinculo = ImportacaoIA.objects.get(modelo='Documento')
        self.assertEqual(vinculo.objeto_id, documento_origem.pk)
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')
        self.assertEqual(vinculo.pagina, 1)
        self.assertEqual(vinculo.lancamento, lancamento)
        self.assertEqual(vinculo.criado_por, self.usuario)

    def test_documento_alheio_do_mesmo_imovel_nao_e_vinculado(self):
        # B2 (#263 rodada 3): o Imovel não é travado — outro escritor pode
        # criar documento no mesmo imóvel durante a importação. O vínculo
        # sai dos IDs que o caminho de criação devolve, nunca do diff dos
        # documentos do imóvel.
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        # Rótulo de MATRÍCULA: com o rótulo prevalecendo (#322 rodada 3),
        # o 'R-1' do payload-base faria o ato virar registro.
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        extracao = self._extracao(payload)
        processar = LancamentoOrigemService.processar_origens_automaticas
        alheios = []

        def com_escritor_concorrente(*args, **kwargs):
            alheios.append(Documento.objects.create(
                imovel=self.imovel, tipo=self.documento.tipo,
                numero=f'M909{len(alheios)}', data=date(2024, 1, 1),
                cartorio=self.documento.cartorio, livro='1', folha='1',
            ))
            return processar(*args, **kwargs)

        with patch.object(
            LancamentoOrigemService, 'processar_origens_automaticas',
            side_effect=com_escritor_concorrente,
        ):
            self._importar(extracao)

        self.assertTrue(alheios)
        (documento_origem,) = Documento.objects.filter(
            imovel=self.imovel, numero='T366',
        )
        self.assertEqual(
            list(
                ImportacaoIA.objects.filter(modelo='Documento')
                .values_list('objeto_id', flat=True)
            ),
            [documento_origem.pk],
        )
