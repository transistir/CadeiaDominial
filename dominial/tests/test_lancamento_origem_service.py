"""``LancamentoOrigemService.vincular_documento_origem`` (#324 / I-11d).

O helper grava ``Lancamento.documento_origem`` a partir da origem estruturada
do lançamento — só a importação assistida o chama (o fluxo manual não grava
essa FK). Contrato: aceita só ``encontrado`` pela identidade COMPLETA (tipo +
número normalizado + cartório) dentro do queryset do chamador; nunca cria
documento, nunca resolve só pelo número, nunca usa ``Documento.objects`` (o
queryset é obrigatório) e grava com ``update()`` — ``save()`` dispararia de
novo o ``post_save`` que reprocessa as origens.
"""

from unittest import mock

from django.test import TestCase
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.documento_identidade_service import (
    ResultadoResolucaoDocumento,
)
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.utils.documento_identidade_utils import DocumentoIdentidade


class VincularDocumentoOrigemTest(TestCase):
    def setUp(self):
        self.ti = TIs.objects.create(nome='TI V324', codigo='V324', etnia='Teste')
        self.ti_alheia = TIs.objects.create(
            nome='TI alheia V324', codigo='V324A', etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa V324')
        self.cartorio_a = Cartorios.objects.create(
            nome='Cartório A V324', cns='324001', cidade='A', estado='SP',
        )
        self.cartorio_b = Cartorios.objects.create(
            nome='Cartório B V324', cns='324002', cidade='B', estado='MS',
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')
        self.imovel_atual = self._imovel(self.ti, pessoa, '324', 'Atual')
        self.imovel_origem = self._imovel(self.ti, pessoa, '325', 'Origem')
        self.imovel_alheio = self._imovel(self.ti_alheia, pessoa, '326', 'Alheio')
        self.documento_atual = self._documento(
            self.imovel_atual, self.tipo_matricula, 'M324', self.cartorio_a,
        )
        self.documento_origem = self._documento(
            self.imovel_origem, self.tipo_transcricao, 'T222', self.cartorio_b,
        )
        # O escopo do "usuário": a TI dele, sem a TI alheia.
        self.escopo = Documento.objects.filter(
            imovel__terra_indigena_id=self.ti,
        )

    def _imovel(self, ti, pessoa, matricula, nome):
        return Imovel.objects.create(
            terra_indigena_id=ti, nome=nome, proprietario=pessoa,
            matricula=matricula, tipo_documento_principal='matricula',
            cartorio=self.cartorio_a,
        )

    @staticmethod
    def _documento(imovel, tipo, numero, cartorio):
        return Documento.objects.create(
            imovel=imovel, tipo=tipo, numero=numero,
            data=timezone.now().date(), cartorio=cartorio,
        )

    def _lancamento(self, tipo='transcricao', numero='T222', cartorio=None):
        """Lançamento sem sinal (``bulk_create``) com UMA origem estruturada."""
        lancamento = Lancamento(
            documento=self.documento_atual, tipo=self.tipo_registro,
            data=timezone.now().date(),
        )
        Lancamento.objects.bulk_create([lancamento])
        if tipo is not None:
            LancamentoOrigem.objects.create(
                lancamento=lancamento, indice_origem=0, tipo_documento=tipo,
                numero=numero, cartorio=cartorio or self.cartorio_b,
            )
        return lancamento

    def _vincular(self, lancamento, escopo=None):
        return LancamentoOrigemService.vincular_documento_origem(
            lancamento,
            documentos_queryset=self.escopo if escopo is None else escopo,
        )

    @staticmethod
    def _fk_no_banco(lancamento):
        return Lancamento.objects.get(pk=lancamento.pk).documento_origem_id

    def test_vincula_o_documento_encontrado_no_escopo(self):
        lancamento = self._lancamento()

        documento = self._vincular(lancamento)

        self.assertEqual(documento, self.documento_origem)
        self.assertEqual(lancamento.documento_origem, self.documento_origem)
        self.assertEqual(
            self._fk_no_banco(lancamento), self.documento_origem.pk,
        )
        self.assertEqual(
            list(self.documento_origem.lancamentos_origem.all()),
            [lancamento],
        )

    def test_numero_com_pontuacao_resolve_pela_identidade_normalizada(self):
        outro = self._documento(
            self.imovel_origem, self.tipo_transcricao, 'T42.718',
            self.cartorio_a,
        )
        lancamento = self._lancamento(
            numero='T42.718', cartorio=self.cartorio_a,
        )

        self.assertEqual(self._vincular(lancamento), outro)

    def test_queryset_e_obrigatorio(self):
        lancamento = self._lancamento()

        with self.assertRaises(TypeError):
            LancamentoOrigemService.vincular_documento_origem(
                lancamento, documentos_queryset=None,
            )
        with self.assertRaises(TypeError):
            LancamentoOrigemService.vincular_documento_origem(lancamento)

        self.assertIsNone(self._fk_no_banco(lancamento))

    def test_nunca_cria_documento(self):
        lancamento = self._lancamento(numero='T999')
        antes = Documento.objects.count()

        self.assertIsNone(self._vincular(lancamento))

        self.assertEqual(Documento.objects.count(), antes)
        self.assertIsNone(self._fk_no_banco(lancamento))

    def test_documento_fora_do_escopo_nao_vincula(self):
        alheio = self._documento(
            self.imovel_alheio, self.tipo_transcricao, 'T777', self.cartorio_b,
        )
        lancamento = self._lancamento(numero='T777')

        self.assertIsNone(self._vincular(lancamento))
        self.assertIsNone(self._fk_no_banco(lancamento))
        self.assertIsNone(self._vincular(lancamento, Documento.objects.none()))

        # A recusa é do ESCOPO, não da identidade: com um escopo que inclui o
        # documento alheio a mesma origem resolve.
        escopo_alheio = Documento.objects.filter(
            imovel__terra_indigena_id=self.ti_alheia,
        )
        self.assertEqual(self._vincular(lancamento, escopo_alheio), alheio)

    def test_nao_resolve_so_pelo_numero(self):
        # Mesmo tipo e número, mas o cartório declarado pela origem é outro.
        self._documento(
            self.imovel_origem, self.tipo_transcricao, 'T555', self.cartorio_a,
        )
        lancamento = self._lancamento(numero='T555', cartorio=self.cartorio_b)

        self.assertIsNone(self._vincular(lancamento))
        self.assertIsNone(self._fk_no_banco(lancamento))

    def test_nao_resolve_homonimo_de_outro_tipo(self):
        self._documento(
            self.imovel_origem, self.tipo_matricula, 'M888', self.cartorio_b,
        )
        lancamento = self._lancamento(
            tipo='transcricao', numero='T888', cartorio=self.cartorio_b,
        )

        self.assertIsNone(self._vincular(lancamento))
        self.assertIsNone(self._fk_no_banco(lancamento))

    def test_ambiguo_nao_vincula(self):
        lancamento = self._lancamento()
        ambiguo = ResultadoResolucaoDocumento(
            status='ambiguo',
            identidade=DocumentoIdentidade(
                'transcricao', 'T222', self.cartorio_b.pk,
            ),
            candidatos=(self.documento_origem, self.documento_atual),
        )

        with mock.patch(
            'dominial.services.lancamento_origem_service'
            '.DocumentoIdentidadeService.resolver',
            return_value=ambiguo,
        ):
            self.assertIsNone(self._vincular(lancamento))

        self.assertIsNone(self._fk_no_banco(lancamento))

    def test_so_vincula_com_exatamente_uma_origem_estruturada(self):
        sem_origem = self._lancamento(tipo=None)
        self.assertIsNone(self._vincular(sem_origem))
        self.assertIsNone(self._fk_no_banco(sem_origem))

        duas = self._lancamento()
        self._documento(
            self.imovel_origem, self.tipo_matricula, 'M100', self.cartorio_a,
        )
        LancamentoOrigem.objects.create(
            lancamento=duas, indice_origem=1, tipo_documento='matricula',
            numero='M100', cartorio=self.cartorio_a,
        )
        self.assertIsNone(self._vincular(duas))
        self.assertIsNone(self._fk_no_banco(duas))

    def test_grava_com_update_sem_save_nem_reprocessar_origens(self):
        lancamento = self._lancamento()

        with mock.patch.object(Lancamento, 'save') as salvar, mock.patch.object(
            LancamentoOrigemService, 'processar_origens_automaticas',
        ) as processar:
            self._vincular(lancamento)

        salvar.assert_not_called()
        processar.assert_not_called()
        self.assertEqual(
            self._fk_no_banco(lancamento), self.documento_origem.pk,
        )

    def test_sem_resolucao_preserva_o_vinculo_que_ja_existe(self):
        lancamento = self._lancamento(numero='T999')
        Lancamento.objects.filter(pk=lancamento.pk).update(
            documento_origem=self.documento_origem,
        )
        lancamento.refresh_from_db()

        self.assertIsNone(self._vincular(lancamento))

        self.assertEqual(
            self._fk_no_banco(lancamento), self.documento_origem.pk,
        )

    def test_repetir_nao_muda_nada(self):
        lancamento = self._lancamento()
        self._vincular(lancamento)

        # Custo fixo por ato: origens + resolução da identidade + UPDATE.
        with self.assertNumQueries(3):
            self.assertEqual(self._vincular(lancamento), self.documento_origem)

        self.assertEqual(
            self._fk_no_banco(lancamento), self.documento_origem.pk,
        )
        # Só os dois do setUp: repetir nunca cria documento.
        self.assertEqual(Documento.objects.count(), 2)


class HomonimoOutroTipoTest(TestCase):
    """#267 (parte IA): a origem declarada não existe no cartório, mas outro
    tipo com o MESMO número existe lá — só dentro do escopo do chamador."""

    def setUp(self):
        self.ti = TIs.objects.create(nome='TI H267', codigo='H267', etnia='Teste')
        self.ti_alheia = TIs.objects.create(
            nome='TI alheia H267', codigo='H267A', etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa H267')
        self.cartorio = Cartorios.objects.create(
            nome='Cartório H267', cns='267001', cidade='A', estado='SP',
        )
        self.outro_cartorio = Cartorios.objects.create(
            nome='Outro cartório H267', cns='267002', cidade='B', estado='MS',
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.ti, nome='Imóvel H267', proprietario=pessoa,
            matricula='267', tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        self.imovel_alheio = Imovel.objects.create(
            terra_indigena_id=self.ti_alheia, nome='Alheio H267',
            proprietario=pessoa, matricula='268',
            tipo_documento_principal='matricula', cartorio=self.cartorio,
        )
        self.escopo = Documento.objects.filter(
            imovel__terra_indigena_id=self.ti,
        )

    def _documento(self, imovel, tipo, numero, cartorio=None):
        return Documento.objects.create(
            imovel=imovel, tipo=tipo, numero=numero,
            data=timezone.now().date(), cartorio=cartorio or self.cartorio,
        )

    def _homonimo(self, tipo='transcricao', numero='T366', cartorio=None,
                  escopo=None):
        return LancamentoOrigemService.homonimo_outro_tipo(
            tipo, numero, cartorio or self.cartorio,
            documentos_queryset=self.escopo if escopo is None else escopo,
        )

    def test_devolve_o_documento_de_outro_tipo_com_o_mesmo_numero(self):
        matricula = self._documento(self.imovel, self.tipo_matricula, 'M366')

        self.assertEqual(self._homonimo(), matricula)

    def test_inverso_matricula_declarada_e_transcricao_existente(self):
        transcricao = self._documento(
            self.imovel, self.tipo_transcricao, 'T366',
        )

        self.assertEqual(
            self._homonimo(tipo='matricula', numero='M366'), transcricao,
        )

    def test_sem_homonimo_devolve_none(self):
        self._documento(self.imovel, self.tipo_matricula, 'M999')

        self.assertIsNone(self._homonimo())

    def test_declarada_que_existe_no_escopo_nao_e_homonimo(self):
        self._documento(self.imovel, self.tipo_matricula, 'M366')
        self._documento(self.imovel, self.tipo_transcricao, 'T366')

        self.assertIsNone(self._homonimo())

    def test_outro_cartorio_nao_e_homonimo(self):
        self._documento(
            self.imovel, self.tipo_matricula, 'M366', self.outro_cartorio,
        )

        self.assertIsNone(self._homonimo())

    def test_homonimo_fora_do_escopo_nao_aparece(self):
        self._documento(self.imovel_alheio, self.tipo_matricula, 'M366')

        self.assertIsNone(self._homonimo())
        self.assertIsNone(self._homonimo(escopo=Documento.objects.none()))

    def test_declarada_que_so_existe_fora_do_escopo_nao_avisa(self):
        # A origem restrita tem aviso próprio; o homônimo visível não pode
        # afirmar que "a declarada não existe no cartório".
        self._documento(self.imovel_alheio, self.tipo_transcricao, 'T366')
        self._documento(self.imovel, self.tipo_matricula, 'M366')

        self.assertIsNone(self._homonimo())

    def test_queryset_e_obrigatorio_e_cartorio_ausente_devolve_none(self):
        with self.assertRaises(TypeError):
            LancamentoOrigemService.homonimo_outro_tipo(
                'transcricao', 'T366', self.cartorio, documentos_queryset=None,
            )
        self.assertIsNone(LancamentoOrigemService.homonimo_outro_tipo(
            'transcricao', 'T366', None, documentos_queryset=self.escopo,
        ))

    def test_numero_incompativel_com_o_tipo_devolve_none(self):
        self._documento(self.imovel, self.tipo_matricula, 'M366')

        # Prefixo T contradiz o tipo informado: sem identidade, sem aviso.
        self.assertIsNone(self._homonimo(tipo='matricula', numero='T366'))
