from dataclasses import FrozenInstanceError
from datetime import date

from django.db import IntegrityError, transaction
from django.core.management import call_command, CommandError
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from io import StringIO
import json
from unittest.mock import patch

from dominial.forms import ImovelForm
from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.documento_identidade_service import DocumentoIdentidadeService
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.services.hierarquia_origem_service import HierarquiaOrigemService
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.utils.documento_identidade_utils import (
    DocumentoIdentidade,
    normalizar_numero_documento,
)
from dominial.utils.hierarquia_utils import (
    identificar_documentos_importados,
    identificar_tronco_principal,
)


class DocumentoIdentidadeValueObjectTest(TestCase):
    def test_ct01_cartorios_diferentes_produzem_identidades_diferentes(self):
        identidade_a = DocumentoIdentidade('matricula', '123', 1)
        identidade_b = DocumentoIdentidade('matricula', '123', 2)

        self.assertNotEqual(identidade_a, identidade_b)

    def test_ct02_tipos_diferentes_produzem_identidades_diferentes(self):
        matricula = DocumentoIdentidade('matricula', 'M123', 1)
        transcricao = DocumentoIdentidade('transcricao', 'T123', 1)

        self.assertNotEqual(matricula, transcricao)

    def test_ct03_formatos_equivalentes_produzem_a_mesma_identidade(self):
        com_prefixo = DocumentoIdentidade(' MATRICULA ', ' M 123 ', 1)
        sem_prefixo = DocumentoIdentidade('matricula', '123', 1)

        self.assertEqual(com_prefixo, sem_prefixo)
        self.assertEqual(hash(com_prefixo), hash(sem_prefixo))

    def test_ct05_recusa_identidade_sem_cartorio(self):
        with self.assertRaises(TypeError):
            DocumentoIdentidade('matricula', '123', None)

    def test_ct05_recusa_identidade_sem_tipo(self):
        with self.assertRaises(TypeError):
            DocumentoIdentidade(None, '123', 1)

    def test_identidade_e_imutavel(self):
        identidade = DocumentoIdentidade('matricula', '123', 1)

        with self.assertRaises(FrozenInstanceError):
            identidade.cartorio_id = 2

    def test_recusa_id_de_cartorio_invalido(self):
        with self.assertRaises(ValueError):
            DocumentoIdentidade('matricula', '123', 0)


class NormalizacaoNumeroDocumentoTest(TestCase):
    def test_ct09_remove_prefixo_m_da_matricula(self):
        self.assertEqual(normalizar_numero_documento("M123", "matricula"), "123")

    def test_ct10_remove_prefixo_e_espacos_de_apresentacao(self):
        self.assertEqual(normalizar_numero_documento("  M 123  ", "matricula"), "123")

    def test_ct11_preserva_zeros_a_esquerda(self):
        self.assertEqual(normalizar_numero_documento("00123", "matricula"), "00123")

    def test_ct12_recusa_prefixo_incompativel_com_tipo(self):
        with self.assertRaisesMessage(ValueError, "incompatível"):
            normalizar_numero_documento("T123", "matricula")

    def test_normaliza_tipo_e_prefixo_sem_diferenciar_maiusculas(self):
        self.assertEqual(normalizar_numero_documento("t123", " TRANSCRICAO "), "123")

    def test_preserva_pontuacao_e_espacos_internos(self):
        self.assertEqual(normalizar_numero_documento("12.345 A", "matricula"), "12.345 A")

    def test_recusa_numero_vazio(self):
        with self.assertRaisesMessage(ValueError, "não pode ser vazio"):
            normalizar_numero_documento("   ", "matricula")

    def test_recusa_apenas_prefixo(self):
        with self.assertRaisesMessage(ValueError, "apenas o prefixo"):
            normalizar_numero_documento(" M ", "matricula")

    def test_recusa_tipo_desconhecido(self):
        with self.assertRaisesMessage(ValueError, "Tipo de documento inválido"):
            normalizar_numero_documento("123", "registro")


class IdentidadeDocumentoFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ti = TIs.objects.create(nome="TI Identidade", codigo="TI-ID", etnia="Teste")
        cls.pessoa = Pessoas.objects.create(nome="Pessoa Identidade", cpf="11111111111")
        cls.cartorio_a = Cartorios.objects.create(
            nome="Cartório A",
            cns="CNS-A",
            cidade="Cidade A",
            estado="MS",
        )
        cls.cartorio_b = Cartorios.objects.create(
            nome="Cartório B",
            cns="CNS-B",
            cidade="Cidade B",
            estado="MT",
        )
        cls.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        cls.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")

    def criar_imovel(self, matricula, cartorio, tipo="matricula", nome="Imóvel"):
        return Imovel.objects.create(
            terra_indigena_id=self.ti,
            nome=nome,
            proprietario=self.pessoa,
            matricula=matricula,
            tipo_documento_principal=tipo,
            cartorio=cartorio,
        )

    def criar_documento(self, imovel, tipo, numero, cartorio):
        return Documento.objects.create(
            imovel=imovel,
            tipo=tipo,
            numero=numero,
            data="2026-01-01",
            cartorio=cartorio,
            livro="1",
            folha="1",
        )


class IdentidadeDocumentoModelTest(IdentidadeDocumentoFixture):
    def test_ct01_mesmo_numero_em_cartorios_diferentes_sao_documentos_distintos(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")

        documento_a = self.criar_documento(imovel_a, self.tipo_matricula, "123", self.cartorio_a)
        documento_b = self.criar_documento(imovel_b, self.tipo_matricula, "123", self.cartorio_b)

        self.assertNotEqual(documento_a.pk, documento_b.pk)
        self.assertNotEqual(documento_a.cartorio_id, documento_b.cartorio_id)

    def test_ct03_identidade_completa_localiza_exatamente_um_documento(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")
        documento_a = self.criar_documento(imovel_a, self.tipo_matricula, "123", self.cartorio_a)
        self.criar_documento(imovel_b, self.tipo_matricula, "123", self.cartorio_b)

        encontrado = Documento.objects.get(
            tipo=self.tipo_matricula,
            numero="123",
            cartorio=self.cartorio_a,
        )

        self.assertEqual(encontrado.pk, documento_a.pk)

    def test_ct04_ordem_de_criacao_nao_afeta_busca_pela_identidade_completa(self):
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        self.criar_documento(imovel_b, self.tipo_matricula, "123", self.cartorio_b)
        documento_a = self.criar_documento(imovel_a, self.tipo_matricula, "123", self.cartorio_a)

        encontrado = Documento.objects.get(
            tipo=self.tipo_matricula,
            numero="123",
            cartorio=self.cartorio_a,
        )

        self.assertEqual(encontrado.pk, documento_a.pk)

    def test_ct02_matricula_e_transcricao_homonimas_no_mesmo_cartorio_devem_coexistir(self):
        """A identidade inclui o tipo estruturado do documento."""
        imovel_m = self.criar_imovel("123", self.cartorio_a, nome="Imóvel M")
        imovel_t = self.criar_imovel("T-123", self.cartorio_a, tipo="transcricao", nome="Imóvel T")
        self.criar_documento(imovel_m, self.tipo_matricula, "123", self.cartorio_a)

        self.criar_documento(imovel_t, self.tipo_transcricao, "123", self.cartorio_a)

    def test_cr01_constraint_recusa_variantes_canonicas_do_documento(self):
        imovel_a = self.criar_imovel("9001", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("9002", self.cartorio_a, nome="Imóvel B")
        documento = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            " M 123 ",
            self.cartorio_a,
        )

        documento.refresh_from_db()
        self.assertEqual(documento.numero, " M 123 ")
        self.assertEqual(documento.numero_normalizado, "123")

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(
                imovel_b,
                self.tipo_matricula,
                "123",
                self.cartorio_a,
            )

    def test_cr03_zeros_a_esquerda_permanecem_identidade_distinta(self):
        imovel_a = self.criar_imovel("9001", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("9002", self.cartorio_a, nome="Imóvel B")

        documento_zeros = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M00123",
            self.cartorio_a,
        )
        documento_sem_zeros = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "123",
            self.cartorio_a,
        )

        documento_zeros.refresh_from_db()
        documento_sem_zeros.refresh_from_db()
        self.assertEqual(documento_zeros.numero_normalizado, "00123")
        self.assertEqual(documento_sem_zeros.numero_normalizado, "123")

    def test_campo_gerado_equivale_ao_normalizador_python(self):
        casos = (
            (self.tipo_matricula, "m123"),
            (self.tipo_transcricao, " T 00123 "),
            (self.tipo_matricula, " 12.345 A "),
        )

        for indice, (tipo, numero) in enumerate(casos, start=1):
            with self.subTest(tipo=tipo.tipo, numero=numero):
                imovel = self.criar_imovel(
                    f"EQ-{indice}",
                    self.cartorio_a,
                    nome=f"Imóvel equivalência {indice}",
                )
                documento = self.criar_documento(
                    imovel,
                    tipo,
                    numero,
                    self.cartorio_a,
                )
                documento.refresh_from_db()

                self.assertEqual(
                    documento.numero_normalizado,
                    normalizar_numero_documento(numero, tipo.tipo),
                )


class IdentidadeImovelFormTest(IdentidadeDocumentoFixture):
    def dados_formulario(self, cartorio, tipo="matricula"):
        return {
            "nome": "Novo imóvel",
            "matricula": "123",
            "tipo_documento_principal": tipo,
            "observacoes": "",
            "proprietario_nome": "Nova pessoa",
            "proprietario": "",
            "estado": cartorio.estado,
            "cidade": cartorio.cidade,
            "cartorio": str(cartorio.pk),
        }

    def test_ct06_formulario_aceita_mesmo_numero_em_cartorio_diferente(self):
        self.criar_imovel("123", self.cartorio_a, nome="Imóvel existente")

        form = ImovelForm(data=self.dados_formulario(self.cartorio_b))

        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_ct08_formulario_recusa_mesma_identidade_no_mesmo_cartorio(self):
        self.criar_imovel("123", self.cartorio_a, nome="Imóvel existente")

        form = ImovelForm(data=self.dados_formulario(self.cartorio_a))

        self.assertFalse(form.is_valid())
        self.assertIn("matricula", form.errors)

    def test_formulario_deve_aceitar_tipo_diferente_com_mesmo_numero_e_cartorio(self):
        self.criar_imovel("123", self.cartorio_a, nome="Matrícula existente")

        form = ImovelForm(data=self.dados_formulario(self.cartorio_a, tipo="transcricao"))

        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_ct07_formulario_recusa_cadastro_sem_cartorio(self):
        dados = self.dados_formulario(self.cartorio_a)
        dados['cartorio'] = ''

        form = ImovelForm(data=dados)

        self.assertFalse(form.is_valid())
        self.assertIn('cartorio', form.errors)

    def test_ct07_modelo_recusa_novo_imovel_sem_cartorio(self):
        total_antes = Imovel.objects.count()

        with self.assertRaisesMessage(
            ValidationError,
            'Cartório é obrigatório para identificar o imóvel.',
        ):
            Imovel.objects.create(
                terra_indigena_id=self.ti,
                nome='Sem cartório',
                proprietario=self.pessoa,
                matricula='999',
                tipo_documento_principal='matricula',
                cartorio=None,
            )

        self.assertEqual(Imovel.objects.count(), total_antes)

    def test_cr02_formulario_e_banco_recusam_matricula_equivalente(self):
        existente = self.criar_imovel(
            "123",
            self.cartorio_a,
            nome="Imóvel existente",
        )
        existente.refresh_from_db()
        self.assertEqual(existente.matricula_normalizada, "123")

        dados = self.dados_formulario(self.cartorio_a)
        dados["matricula"] = " M 123 "
        form = ImovelForm(data=dados)

        self.assertFalse(form.is_valid())
        self.assertIn("matricula", form.errors)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_imovel(
                "M123",
                self.cartorio_a,
                nome="Duplicado canônico",
            )

    def test_constraint_atual_recusa_documento_duplicado_no_mesmo_cartorio(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("456", self.cartorio_a, nome="Imóvel B")
        self.criar_documento(imovel_a, self.tipo_matricula, "123", self.cartorio_a)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(imovel_b, self.tipo_matricula, "123", self.cartorio_a)


class AuditoriaIdentidadeDocumentosCommandTest(IdentidadeDocumentoFixture):
    def test_comando_confirma_ausencia_de_conflito_sem_escrever(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        saida = StringIO()

        with CaptureQueriesContext(connection) as consultas:
            call_command(
                "auditar_identidade_documentos",
                "--json",
                stdout=saida,
            )

        relatorio = json.loads(saida.getvalue())
        self.assertTrue(relatorio["somente_leitura"])
        self.assertEqual(relatorio["total_grupos_conflitantes"], 0)
        self.assertEqual(relatorio["total_documentos_conflitantes"], 0)
        comandos_escrita = ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP")
        self.assertFalse(any(
            consulta["sql"].lstrip().upper().startswith(comandos_escrita)
            for consulta in consultas.captured_queries
        ))

    def test_comando_relata_numero_invalido(self):
        imovel = self.criar_imovel("123", self.cartorio_a)
        self.criar_documento(
            imovel,
            self.tipo_matricula,
            "T123",
            self.cartorio_a,
        )
        saida = StringIO()

        call_command("auditar_identidade_documentos", "--json", stdout=saida)

        relatorio = json.loads(saida.getvalue())
        self.assertEqual(relatorio["total_invalidos"], 1)
        self.assertIn("incompatível", relatorio["invalidos"][0]["erro"])

    def test_fail_on_conflict_interrompe_diante_de_invalido_sem_corrigir(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        documento = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "T123",
            self.cartorio_a,
        )

        with self.assertRaises(CommandError):
            call_command(
                "auditar_identidade_documentos",
                "--fail-on-conflict",
                stdout=StringIO(),
            )

        documento.refresh_from_db()
        self.assertEqual(documento.numero, "T123")


class VerificarEstruturaAmbienteCommandTest(TestCase):
    def test_comando_relata_migracoes_e_constraints_sem_escrever(self):
        saida = StringIO()

        with CaptureQueriesContext(connection) as consultas:
            call_command(
                "verificar_estrutura_ambiente",
                "--json",
                stdout=saida,
            )

        relatorio = json.loads(saida.getvalue())
        self.assertTrue(relatorio["somente_leitura"])
        self.assertEqual(relatorio["database"], "default")
        self.assertEqual(relatorio["migracoes_pendentes"], [])
        self.assertIn("dominial_documento", relatorio["constraints_unicas"])
        self.assertIn("dominial_imovel", relatorio["constraints_unicas"])
        self.assertIn("dominial_lancamentoorigem", relatorio["constraints_unicas"])
        comandos_escrita = ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP")
        self.assertFalse(any(
            consulta["sql"].lstrip().upper().startswith(comandos_escrita)
            for consulta in consultas.captured_queries
        ))

    def test_expect_final_aprova_quando_constraints_finais_estao_presentes(self):
        saida = StringIO()

        call_command(
            "verificar_estrutura_ambiente",
            "--expect-final",
            "--json",
            stdout=saida,
        )

        relatorio = json.loads(saida.getvalue())
        self.assertTrue(all(
            estado["atendida"]
            for estado in relatorio["expectativas_finais"].values()
        ))


class DocumentoIdentidadeServiceTest(IdentidadeDocumentoFixture):
    def test_ct13_resolve_somente_documento_do_tipo_numero_e_cartorio_informados(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")
        self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )

        resultado = DocumentoIdentidadeService.resolver_por_dados(
            tipo="matricula",
            numero="123",
            cartorio_id=self.cartorio_b.pk,
        )

        self.assertEqual(resultado.status, "encontrado")
        self.assertEqual(resultado.documento.pk, documento_b.pk)
        self.assertEqual(resultado.documento.cartorio_id, self.cartorio_b.pk)

    def test_ct14_retorna_nao_encontrado_para_identidade_inexistente(self):
        resultado = DocumentoIdentidadeService.resolver_por_dados(
            tipo="matricula",
            numero="999",
            cartorio_id=self.cartorio_a.pk,
        )

        self.assertEqual(resultado.status, "nao_encontrado")
        self.assertIsNone(resultado.documento)
        self.assertEqual(resultado.candidatos, ())

    def test_ct15_constraint_impede_estado_ambiguo_pos_migracao(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("456", self.cartorio_a, nome="Imóvel B")
        documento_prefixado = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(
                imovel_b,
                self.tipo_matricula,
                "123",
                self.cartorio_a,
            )

        resultado = DocumentoIdentidadeService.resolver_por_dados(
            tipo="matricula",
            numero="123",
            cartorio_id=self.cartorio_a.pk,
        )

        self.assertEqual(resultado.status, "encontrado")
        self.assertEqual(resultado.documento, documento_prefixado)
        self.assertEqual(resultado.candidatos, (documento_prefixado,))

    def test_resolucao_distingue_tipo_do_documento(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        documento = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )

        resultado = DocumentoIdentidadeService.resolver_por_dados(
            tipo="transcricao",
            numero="123",
            cartorio_id=self.cartorio_a.pk,
        )

        self.assertEqual(resultado.status, "nao_encontrado")
        self.assertNotEqual(resultado.documento, documento)

    def test_cr08_candidato_invalido_nao_oculta_candidato_valido(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        documento_valido = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_invalido = Documento(
            pk=999999,
            imovel=imovel,
            tipo=self.tipo_matricula,
            numero="T123",
            data=date(2026, 1, 1),
            cartorio=self.cartorio_a,
            livro="1",
            folha="1",
        )

        with patch.object(Documento.objects, "filter") as filtrar:
            filtrar.return_value.select_related.return_value.order_by.return_value = (
                documento_invalido,
                documento_valido,
            )
            resultado = DocumentoIdentidadeService.resolver_por_dados(
                tipo="matricula",
                numero="123",
                cartorio_id=self.cartorio_a.pk,
            )

        self.assertEqual(resultado.status, "encontrado")
        self.assertEqual(resultado.documento, documento_valido)
        self.assertEqual(resultado.candidatos, (documento_valido,))
        self.assertEqual(resultado.candidatos_invalidos, (documento_invalido,))

    def test_cr08_candidato_invalido_persistido_retorna_resultado_controlado(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel inválido")
        documento_invalido = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "T123",
            self.cartorio_a,
        )

        resultado = DocumentoIdentidadeService.resolver_por_dados(
            tipo="matricula",
            numero="123",
            cartorio_id=self.cartorio_a.pk,
        )

        self.assertEqual(resultado.status, "nao_encontrado")
        self.assertIsNone(resultado.documento)
        self.assertEqual(resultado.candidatos, ())
        self.assertEqual(resultado.candidatos_invalidos, (documento_invalido,))

    def test_resolucao_recusa_dados_incompletos(self):
        with self.assertRaises(TypeError):
            DocumentoIdentidadeService.resolver_por_dados("matricula", "123", None)

    def test_resolver_exige_objeto_de_identidade(self):
        with self.assertRaisesMessage(TypeError, "DocumentoIdentidade completo"):
            DocumentoIdentidadeService.resolver("matricula:123:1")


class OrigensDisponiveisTabelaTest(IdentidadeDocumentoFixture):
    def test_ct16_origem_disponivel_usa_documento_do_cartorio_informado(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")
        self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )

        origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
            "M123",
            imovel_b,
            cartorio_origem=self.cartorio_b,
        )

        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0]["documento"].pk, documento_b.pk)
        self.assertEqual(origens[0]["documento"].cartorio_id, self.cartorio_b.pk)

    def test_origem_sem_cartorio_nao_seleciona_documento(self):
        imovel = self.criar_imovel("123", self.cartorio_a)
        self.criar_documento(imovel, self.tipo_matricula, "M123", self.cartorio_a)

        origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
            "M123",
            imovel,
            cartorio_origem=None,
        )

        self.assertEqual(origens, [])

    def test_constraint_impede_origem_ambigua_na_tabela(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("456", self.cartorio_a, nome="Imóvel B")
        documento = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(
                imovel_b,
                self.tipo_matricula,
                "123",
                self.cartorio_a,
            )

        origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
            "M123",
            imovel_a,
            cartorio_origem=self.cartorio_a,
        )

        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0]["documento"], documento)

    def test_origem_respeita_tipo_extraido_do_prefixo(self):
        imovel = self.criar_imovel("123", self.cartorio_a)
        self.criar_documento(imovel, self.tipo_matricula, "M123", self.cartorio_a)

        origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
            "T123",
            imovel,
            cartorio_origem=self.cartorio_a,
        )

        self.assertEqual(origens, [])

    def test_ct16_expansao_da_tabela_nao_importa_homonimo_de_outro_cartorio(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_b,
            )
        ])

        cadeia = CadeiaDominialTabelaService()._expandir_tronco_com_importados(
            imovel_atual,
            [documento_atual],
        )

        self.assertIn(documento_b, cadeia)
        self.assertNotIn(documento_a, cadeia)


@override_settings(DUPLICATA_VERIFICACAO_ENABLED=True)
class DuplicataIdentidadeDocumentoTest(IdentidadeDocumentoFixture):
    def test_ct17_homonimo_de_outro_cartorio_nao_e_duplicata(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_b, nome="Atual")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )

        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem="M123",
            cartorio_id=self.cartorio_b.pk,
            imovel_atual_id=imovel_atual.pk,
        )

        self.assertFalse(resultado["tem_duplicata"])

    def test_duplicata_normaliza_numero_e_respeita_tipo(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Origem")
        documento = self.criar_documento(
            imovel_origem,
            self.tipo_matricula,
            "123",
            self.cartorio_a,
        )

        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem="M123",
            cartorio_id=self.cartorio_a.pk,
            imovel_atual_id=imovel_atual.pk,
        )

        self.assertTrue(resultado["tem_duplicata"])
        self.assertEqual(resultado["documento_origem"].pk, documento.pk)

        resultado_transcricao = (
            DuplicataVerificacaoService.verificar_duplicata_origem(
                origem="T123",
                cartorio_id=self.cartorio_a.pk,
                imovel_atual_id=imovel_atual.pk,
            )
        )
        self.assertFalse(resultado_transcricao["tem_duplicata"])

    def test_origem_numerica_sem_prefixo_e_tratada_como_matricula_implicita(self):
        """Achado da revisão automatizada do PR (Codex, 2026-07-14): uma
        origem digitada só com números (sem "M"/"T") já é tratada como
        matrícula implícita em outros pontos do sistema
        (`LancamentoOrigemLeituraService._extrair_identidade_legada`); a
        detecção de duplicata precisa fazer o mesmo, senão um documento
        existente com o mesmo número normalizado/cartório não é detectado
        como duplicata quando o usuário digita "123" em vez de "M123"."""
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Origem")
        documento = self.criar_documento(
            imovel_origem,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )

        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem="123",
            cartorio_id=self.cartorio_a.pk,
            imovel_atual_id=imovel_atual.pk,
        )

        self.assertTrue(resultado["tem_duplicata"])
        self.assertEqual(resultado["documento_origem"].pk, documento.pk)

    def test_ct18_documentos_importaveis_nao_cruzam_cartorios(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_b,
            )
        ])

        documentos = DuplicataVerificacaoService.calcular_documentos_importaveis(
            documento_atual,
        )

        self.assertIn(documento_b, documentos)
        self.assertNotIn(documento_a, documentos)


class CriacaoAutomaticaOrigemTest(IdentidadeDocumentoFixture):
    def criar_lancamento_multiplas_origens(self, origem, livro="GERAL", folha="GERAL"):
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual múltiplas")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem=origem,
            cartorio_origem=self.cartorio_a,
            livro_origem=livro,
            folha_origem=folha,
        )
        Lancamento.objects.bulk_create([lancamento])
        return imovel, lancamento

    def test_cr07_multiplas_origens_preservam_livro_e_folha_individuais(self):
        from django.core.cache import cache

        imovel, lancamento = self.criar_lancamento_multiplas_origens(
            "M101; T202",
        )
        cache.set(
            f"mapeamento_origens_lancamento_{lancamento.pk}",
            [
                {
                    "origem": "M101",
                    "cartorio_id": self.cartorio_a.pk,
                    "cartorio_nome": self.cartorio_a.nome,
                    "livro": " 11 ",
                    "folha": " 111 ",
                },
                {
                    "origem": "T202",
                    "cartorio_id": self.cartorio_b.pk,
                    "cartorio_nome": self.cartorio_b.nome,
                    "livro": "22",
                    "folha": "222",
                },
            ],
            timeout=3600,
        )

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento,
            lancamento.origem,
            imovel,
        )

        documento_m = Documento.objects.get(
            tipo=self.tipo_matricula,
            numero_normalizado="101",
            cartorio=self.cartorio_a,
        )
        documento_t = Documento.objects.get(
            tipo=self.tipo_transcricao,
            numero_normalizado="202",
            cartorio=self.cartorio_b,
        )
        self.assertEqual((documento_m.livro, documento_m.folha), ("11", "111"))
        self.assertEqual((documento_t.livro, documento_t.folha), ("22", "222"))

    def test_multiplas_origens_usam_metadados_gerais_como_fallback(self):
        from django.core.cache import cache

        imovel, lancamento = self.criar_lancamento_multiplas_origens(
            "M303; T404",
            livro=" 77 ",
            folha=" 88 ",
        )
        cache.set(
            f"mapeamento_origens_lancamento_{lancamento.pk}",
            [
                {
                    "origem": origem,
                    "cartorio_id": cartorio.pk,
                    "cartorio_nome": cartorio.nome,
                    "livro": "",
                    "folha": None,
                }
                for origem, cartorio in (
                    ("M303", self.cartorio_a),
                    ("T404", self.cartorio_b),
                )
            ],
            timeout=3600,
        )

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento,
            lancamento.origem,
            imovel,
        )

        documentos = Documento.objects.filter(
            numero_normalizado__in=("303", "404"),
        )
        self.assertEqual(documentos.count(), 2)
        self.assertEqual(
            {(documento.livro, documento.folha) for documento in documentos},
            {("77", "88")},
        )

    def test_ct19_homonimo_em_a_nao_impede_criacao_em_b_nem_muda_cartorio(self):
        imovel = self.criar_imovel("999", self.cartorio_b, nome="Atual")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_b,
        )
        documento_a = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )
        Lancamento.objects.bulk_create([lancamento])

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento,
            lancamento.origem,
            imovel,
        )

        documento_a.refresh_from_db()
        documento_b = Documento.objects.get(
            tipo=self.tipo_matricula,
            numero="M123",
            cartorio=self.cartorio_b,
        )
        self.assertEqual(documento_b.cartorio_id, self.cartorio_b.pk)
        self.assertEqual(documento_a.cartorio_id, self.cartorio_a.pk)
        self.assertNotEqual(documento_a.pk, documento_b.pk)

    def test_ct19_identidade_existente_em_b_nao_e_duplicada(self):
        imovel = self.criar_imovel("999", self.cartorio_b, nome="Atual")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_b,
        )
        documento_b = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )
        Lancamento.objects.bulk_create([lancamento])

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento,
            lancamento.origem,
            imovel,
        )

        candidatos = Documento.objects.filter(
            tipo=self.tipo_matricula,
            numero="M123",
            cartorio=self.cartorio_b,
        )
        self.assertEqual(candidatos.count(), 1)
        self.assertEqual(candidatos.get().pk, documento_b.pk)

    def test_ct20_inicio_em_b_nao_altera_homonimo_sem_lancamentos_em_a(self):
        imovel = self.criar_imovel("999", self.cartorio_b, nome="Atual")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_b,
        )
        documento_a = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_a.observacoes = "registro original"
        documento_a.save(update_fields=["observacoes"])
        self.assertFalse(documento_a.lancamentos.exists())

        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data="2026-01-02",
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )
        Lancamento.objects.bulk_create([lancamento])

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento,
            lancamento.origem,
            imovel,
        )

        documento_a.refresh_from_db()
        self.assertEqual(documento_a.cartorio_id, self.cartorio_a.pk)
        self.assertEqual(documento_a.observacoes, "registro original")
        self.assertTrue(
            Documento.objects.filter(
                tipo=self.tipo_matricula,
                numero="M123",
                cartorio=self.cartorio_b,
            ).exists()
        )


class HierarquiaOrigemIdentidadeTest(IdentidadeDocumentoFixture):
    def test_ct16_hierarquia_resolve_origem_no_cartorio_do_lancamento(self):
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )

        origem = HierarquiaOrigemService._processar_origem_individual(
            imovel,
            lancamento,
            {"tipo": "matricula", "numero": "M123"},
        )

        self.assertEqual(origem["documento_id"], documento_b.pk)
        self.assertNotEqual(origem["documento_id"], documento_a.pk)

    def test_ct19_hierarquia_cria_b_sem_alterar_homonimo_a(self):
        imovel = self.criar_imovel("999", self.cartorio_b, nome="Atual")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_b,
        )
        documento_a = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        lancamento = Lancamento(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )

        origem = HierarquiaOrigemService._processar_origem_individual(
            imovel,
            lancamento,
            {"tipo": "matricula", "numero": "M123"},
            criar_documentos_automaticos=True,
        )

        documento_a.refresh_from_db()
        documento_b = Documento.objects.get(pk=origem["documento_id"])
        self.assertEqual(documento_b.cartorio_id, self.cartorio_b.pk)
        self.assertEqual(documento_a.cartorio_id, self.cartorio_a.pk)


class ArvoreIdentidadeDocumentoTest(IdentidadeDocumentoFixture):
    def criar_cenario_homonimos(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=tipo_inicio,
                data=date(2026, 1, 2),
                origem="M123",
                cartorio_origem=self.cartorio_b,
            )
        ])
        return imovel_atual, documento_atual, documento_a, documento_b

    def criar_cenario_cr05(self, criar_origem_b_primeiro):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual CR05")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B CR05")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )

        def criar_documento_a():
            return self.criar_documento(
                imovel_atual,
                self.tipo_matricula,
                "M123",
                self.cartorio_a,
            )

        def criar_documento_b():
            return self.criar_documento(
                imovel_b,
                self.tipo_matricula,
                "M123",
                self.cartorio_b,
            )

        if criar_origem_b_primeiro:
            documento_b = criar_documento_b()
            documento_a = criar_documento_a()
        else:
            documento_a = criar_documento_a()
            documento_b = criar_documento_b()

        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.create(
            documento=documento_atual,
            tipo=tipo_inicio,
            data=date(2026, 1, 2),
            origem="M123",
            cartorio_origem=self.cartorio_b,
        )
        return imovel_atual, documento_atual, documento_a, documento_b

    def test_ct18_arvore_resolve_pai_no_cartorio_do_lancamento(self):
        imovel, documento_atual, documento_a, documento_b = (
            self.criar_cenario_homonimos()
        )

        pais = HierarquiaArvoreService._buscar_documentos_pais(
            documento_atual,
            imovel,
            criar_documentos_automaticos=False,
        )

        self.assertIn(documento_b, pais)
        self.assertNotIn(documento_a, pais)

    def test_cr06_arestas_e_niveis_distinguem_homonimos_por_id(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual CR06")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A CR06")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B CR06")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.bulk_create(
            [
                Lancamento(
                    documento=documento_atual,
                    tipo=tipo_inicio,
                    data=date(2026, 1, 2),
                    origem="M123",
                    cartorio_origem=self.cartorio_a,
                ),
                Lancamento(
                    documento=documento_atual,
                    tipo=tipo_inicio,
                    data=date(2026, 1, 3),
                    origem="M123",
                    cartorio_origem=self.cartorio_b,
                ),
            ]
        )

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            imovel_atual,
        )

        self.assertEqual(
            {(conexao["from"], conexao["to"]) for conexao in arvore["conexoes"]},
            {
                (documento_atual.pk, documento_a.pk),
                (documento_atual.pk, documento_b.pk),
            },
        )
        self.assertTrue(
            all(
                isinstance(conexao["from"], int)
                and isinstance(conexao["to"], int)
                for conexao in arvore["conexoes"]
            )
        )
        nos = {no["id"]: no for no in arvore["documentos"]}
        self.assertEqual(nos[documento_a.pk]["nivel"], 1)
        self.assertEqual(nos[documento_b.pk]["nivel"], 1)
        self.assertEqual(nos[documento_a.pk]["numero"], "M123")
        self.assertEqual(nos[documento_b.pk]["numero"], "M123")

    def test_ct18_cadeia_completa_resolve_origem_no_cartorio_correto(self):
        _, documento_atual, documento_a, documento_b = (
            self.criar_cenario_homonimos()
        )

        origens = CadeiaCompletaService()._expandir_todas_origens_documento(
            documento_atual,
        )

        self.assertIn(documento_b, origens)
        self.assertNotIn(documento_a, origens)

    def test_ct18_documentos_importados_usam_identidade_e_id_processado(self):
        imovel, _, documento_a, documento_b = self.criar_cenario_homonimos()

        importados = identificar_documentos_importados(imovel)

        self.assertIn(documento_b, importados)
        self.assertNotIn(documento_a, importados)

    def test_ct18_tronco_principal_nao_seleciona_homonimo(self):
        imovel, documento_atual, documento_a, documento_b = (
            self.criar_cenario_homonimos()
        )

        tronco = identificar_tronco_principal(imovel)

        self.assertEqual(tronco[0], documento_atual)
        self.assertIn(documento_b, tronco)
        self.assertNotIn(documento_a, tronco)

    def test_cr05_tronco_segue_cartorio_do_lancamento_com_a_criado_primeiro(self):
        imovel, documento_atual, documento_a, documento_b = (
            self.criar_cenario_cr05(criar_origem_b_primeiro=False)
        )

        tronco = identificar_tronco_principal(imovel)

        self.assertEqual(tronco, [documento_atual, documento_b])
        self.assertNotIn(documento_a, tronco)

    def test_cr05_escolha_textual_so_considera_origem_contextual(self):
        imovel, documento_atual, documento_a, documento_b = (
            self.criar_cenario_cr05(criar_origem_b_primeiro=True)
        )

        tronco = identificar_tronco_principal(
            imovel,
            {str(documento_atual.pk): "M123"},
        )

        self.assertEqual(tronco, [documento_atual, documento_b])
        self.assertNotIn(documento_a, tronco)

    def test_escolha_sem_lancamento_nao_busca_documento_por_numero(self):
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Sem origem")
        documento_atual = self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        self.criar_documento(
            imovel,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )

        tronco = identificar_tronco_principal(
            imovel,
            {str(documento_atual.pk): "M123"},
        )

        self.assertEqual(tronco, [documento_atual])

    def test_ct18_cadeia_da_origem_nao_cruza_cartorios(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B")
        documento_atual = self.criar_documento(
            imovel_atual,
            self.tipo_matricula,
            "M999",
            self.cartorio_a,
        )
        documento_a = self.criar_documento(
            imovel_a,
            self.tipo_matricula,
            "M123",
            self.cartorio_a,
        )
        documento_b = self.criar_documento(
            imovel_b,
            self.tipo_matricula,
            "M123",
            self.cartorio_b,
        )
        tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_b,
            )
        ])

        cadeia = DuplicataVerificacaoService.obter_cadeia_dominial_origem(
            documento_atual,
        )
        documentos = [item["documento"] for item in cadeia]

        self.assertIn(documento_atual, documentos)
        self.assertIn(documento_b, documentos)
        self.assertNotIn(documento_a, documentos)
