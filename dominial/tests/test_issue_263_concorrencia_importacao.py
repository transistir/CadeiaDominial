"""
Issue #263 (I-6, rodadas 2 e 3) — corrida importação IA × cadastro manual.

A importação assistida trava o ``Documento`` (``select_for_update``) dentro
da transação antes de checar duplicidade e gravar; o cadastro manual checava
ANTES da transação, sem trava — os dois fluxos podiam gravar o mesmo número
de lançamento no mesmo documento.

Fix: a criação manual trava o ``Documento`` DENTRO do atomic e revalida a
duplicidade depois da trava — SEMPRE, inclusive com ``apos_importacao``
(rodada 3: a flag é da importação de CADEIA e não autoriza duplicata).
Ordem de travas do sistema (a mesma da exclusão do PDF e da importação da
IA): ``DocumentoDigital`` → extração → ``Documento`` — a criação manual só
toma a última.

A trava é provada pela consulta EXECUTADA (``travas_executadas`` espia o
compilador): um ``select_for_update()`` que nunca é avaliado não trava nada.
A concorrência real (2 conexões PostgreSQL) fica em
``ia_ocr.tests.test_importacao`` — pulada no sqlite.
"""
import io
from contextlib import contextmanager, redirect_stdout
from datetime import date
from unittest.mock import patch

from django.db.models.sql.compiler import SQLCompiler
from django.test import RequestFactory

from dominial.models import Documento, Lancamento, LancamentoTipo
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture
from dominial.utils.hierarquia_utils import processar_origens_para_documentos


@contextmanager
def travas_executadas(antes_da_trava=None):
    """Lista ``(modelo, of)`` de cada ``SELECT ... FOR UPDATE`` EXECUTADO.

    Espia o compilador, não o ``select_for_update()``: queryset travado que
    nunca é avaliado não trava nada — sem o ``.get()`` a lista fica vazia e
    ``antes_da_trava`` nunca roda. ``antes_da_trava(modelo)`` roda logo antes
    de cada trava: é o instante em que o escritor concorrente, que segurava
    a trava, commita e a libera. No sqlite o SQL não leva ``FOR UPDATE``,
    mas a consulta executada carrega a intenção (``select_for_update_of``).
    """
    executar = SQLCompiler.execute_sql
    travas = []

    def espia(compilador, *args, **kwargs):
        consulta = compilador.query
        if consulta.select_for_update:
            if antes_da_trava is not None:
                antes_da_trava(consulta.model)
            travas.append((consulta.model, tuple(consulta.select_for_update_of)))
        return executar(compilador, *args, **kwargs)

    with patch.object(SQLCompiler, 'execute_sql', new=espia):
        yield travas


class Issue263Base(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_registro, _ = LancamentoTipo.objects.get_or_create(
            tipo="registro",
        )

    def _criar_cenario(self, matricula="263"):
        imovel = self.criar_imovel(
            matricula, self.cartorio_a, nome=f"Imóvel #{matricula}",
        )
        documento = self.criar_documento(
            imovel, self.tipo_matricula, f"M{matricula}", self.cartorio_a,
        )
        return imovel, documento

    def _post_manual(self, documento, sigla="M263", simples="1", **extras):
        return {
            "tipo_lancamento": str(self.tipo_registro.pk),
            "sigla_matricula": sigla,
            "numero_lancamento_simples": simples,
            "numero_lancamento": "",
            "data": "2026-02-15",
            "observacoes": "",
            "origem_completa[]": [],
            "cartorio_origem[]": [],
            "cartorio_origem_nome[]": [],
            "livro_origem[]": [],
            "folha_origem[]": [],
            "transmitente_nome[]": [],
            "transmitente[]": [],
            "adquirente_nome[]": [],
            "adquirente[]": [],
            **extras,
        }


class RechecagemAposTravaTest(Issue263Base):
    """A duplicidade é rechecada DEPOIS da trava executada, dentro do atomic."""

    def _criar_com_importacao_na_janela(self, matricula, **kwargs):
        """Cadastro manual com a importação IA commitando na janela.

        O papel da importação: entre a checagem prévia (fora da transação)
        e a trava do fluxo manual, ela grava o MESMO número no MESMO
        documento e libera a trava — o que o manual vê depois de travar.
        """
        imovel, documento = self._criar_cenario(matricula=matricula)
        request = RequestFactory().post(
            "/x/", self._post_manual(documento, sigla=f"M{matricula}"),
        )
        request.user = usuario_com_tis(f't{matricula}', self.ti)

        def importacao_commita(modelo):
            if modelo is Documento and not Lancamento.objects.exists():
                Lancamento.objects.create(
                    documento=documento,
                    tipo=self.tipo_registro,
                    numero_lancamento=f"R1 M{matricula}",
                    data=date(2026, 2, 15),
                )

        with travas_executadas(importacao_commita) as travas:
            resultado = LancamentoCriacaoService.criar_lancamento_completo(
                request, self.ti, imovel, documento, **kwargs,
            )
        self.assertIn((Documento, ()), travas)
        return resultado

    def test_duplicata_criada_na_janela_e_pega_pela_rechecagem(self):
        resultado, msg = self._criar_com_importacao_na_janela("26301")

        self.assertIsNone(resultado)
        self.assertIn("Já existe um lançamento", msg)
        self.assertIn("Nenhum lançamento foi salvo", msg)
        # O rollback do atomic desfaz também o registro simulado.
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_apos_importacao_tambem_recheca_sob_a_trava(self):
        # ``apos_importacao`` é a importação de CADEIA (duplicata_views):
        # ela não autoriza gravar o número que a importação IA acabou de
        # gravar — o manual bloqueia com a mensagem do sistema (rodada 3).
        resultado, msg = self._criar_com_importacao_na_janela(
            "26304", apos_importacao=True,
        )

        self.assertIsNone(resultado)
        self.assertIn(
            'Já existe um lançamento com o número "R1 M26304" neste documento',
            msg,
        )
        self.assertIn("Nenhum lançamento foi salvo", msg)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_criacao_manual_trava_o_documento_antes_de_gravar(self):
        imovel, documento = self._criar_cenario(matricula="26302")
        request = RequestFactory().post(
            "/x/", self._post_manual(documento, sigla="M26302"),
        )
        request.user = usuario_com_tis('t263b', self.ti)
        gravados_na_trava = []

        def contar(modelo):
            if modelo is Documento:
                gravados_na_trava.append(
                    Lancamento.objects.filter(documento=documento).count()
                )

        with travas_executadas(contar) as travas:
            resultado, _ = LancamentoCriacaoService.criar_lancamento_completo(
                request, self.ti, imovel, documento,
            )

        # Uma trava do Documento, executada ANTES do INSERT do lançamento.
        self.assertEqual(
            [trava for trava in travas if trava[0] is Documento],
            [(Documento, ())],
        )
        self.assertEqual(gravados_na_trava, [0])
        self.assertIsNotNone(resultado)

    def test_documento_e_relido_depois_da_trava(self):
        # A instância do caller foi lida antes da trava; outro escritor
        # definiu o livro e commitou. Sem reler, a regra pétrea vê o livro
        # vazio e o ``documento.save()`` sobrescreve o livro gravado.
        imovel, documento = self._criar_cenario(matricula="26305")
        Documento.objects.filter(pk=documento.pk).update(livro="0")
        documento.refresh_from_db()
        Documento.objects.filter(pk=documento.pk).update(livro="7")
        request = RequestFactory().post(
            "/x/",
            self._post_manual(
                documento, sigla="M26305", livro_documento="99",
            ),
        )
        request.user = usuario_com_tis('t26305', self.ti)

        resultado, _ = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento,
        )

        self.assertIsNotNone(resultado)
        self.assertEqual(Documento.objects.get(pk=documento.pk).livro, "7")
        self.assertEqual(documento.livro, "7")


class DocumentosCriadosRegistradosTest(Issue263Base):
    """B2 (#263 rodada 3): o caminho de criação devolve os IDs que criou.

    O vínculo de auditoria da importação não pode depender do diff dos
    documentos do imóvel (que não está travado): o próprio caminho de
    criação registra na instância o documento de origem que criou —
    inclusive o criado pelo sinal ``post_save`` durante o save.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_inicio, _ = LancamentoTipo.objects.get_or_create(
            tipo="inicio_matricula",
        )

    def test_documento_criado_no_save_fica_registrado_na_instancia(self):
        imovel, documento = self._criar_cenario(matricula="26306")
        lancamento = Lancamento(
            documento=documento, tipo=self.tipo_inicio,
            data=date(2026, 2, 15), origem="M4321",
            cartorio_origem=self.cartorio_a,
        )

        lancamento.save()  # o sinal post_save cria o documento de origem

        (criado,) = Documento.objects.filter(imovel=imovel, numero="M4321")
        self.assertEqual(
            LancamentoOrigemService.consumir_documentos_criados(lancamento),
            (criado.pk,),
        )
        # Consumir limpa: o registro vive só na operação corrente.
        self.assertEqual(
            LancamentoOrigemService.consumir_documentos_criados(lancamento),
            (),
        )

    def test_documento_reaproveitado_nao_e_registrado(self):
        imovel, documento = self._criar_cenario(matricula="26307")
        self.criar_documento(
            imovel, self.tipo_matricula, "M4322", self.cartorio_a,
        )
        lancamento = Lancamento(
            documento=documento, tipo=self.tipo_inicio,
            data=date(2026, 2, 15), origem="M4322",
            cartorio_origem=self.cartorio_a,
        )

        lancamento.save()
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel,
            documentos_queryset=Documento.objects.all(),
        )

        self.assertEqual(
            LancamentoOrigemService.consumir_documentos_criados(lancamento),
            (),
        )


class StdoutSemValorDocumentalTest(Issue263Base):
    """P2-9: avisos da hierarquia não imprimem número/tipo de documento."""

    def test_avisos_da_hierarquia_usam_somente_ids_tecnicos(self):
        imovel, documento = self._criar_cenario(matricula="26303")
        lancamento = Lancamento.objects.create(
            documento=documento, tipo=self.tipo_registro,
            data=date(2026, 2, 15),
        )
        # Documento que existe em OUTRO imóvel (4º aviso, do resolver).
        self.criar_documento(
            self.criar_imovel("900", self.cartorio_a, nome="Imóvel M900"),
            self.tipo_matricula, "M900", self.cartorio_a,
        )

        saida = io.StringIO()
        with redirect_stdout(saida):
            processar_origens_para_documentos(
                'M777', imovel, lancamento, self.cartorio_a,
                documentos_queryset=Documento.objects.all(),
            )
            processar_origens_para_documentos(
                '888', imovel, lancamento, self.cartorio_a,
                documentos_queryset=Documento.objects.all(),
            )
            processar_origens_para_documentos(
                'M900', imovel, lancamento, self.cartorio_a,
                documentos_queryset=Documento.objects.all(),
            )
            # Texto livre com número (VALIDAÇÃO 4): o aviso de documento
            # inexistente também sai só com o id técnico (rodada 3).
            processar_origens_para_documentos(
                'transcrição 6464 do livro antigo', imovel, lancamento,
                self.cartorio_a, documentos_queryset=Documento.objects.all(),
            )

        texto = saida.getvalue()
        # Número de documento (com ou sem prefixo) nunca vai para o stdout.
        self.assertNotIn('777', texto)
        self.assertNotIn('888', texto)
        self.assertNotIn('900', texto)
        self.assertNotIn('6464', texto)
        self.assertIn(
            f'Documento de origem do lançamento {lancamento.pk} não existe',
            texto,
        )
        # O aviso continua existindo — só que com id técnico do lançamento.
        self.assertIn(str(lancamento.pk), texto)
