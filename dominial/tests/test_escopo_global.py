"""
Teste T11 do contrato — validação de ESCOPO_GLOBAL

(a) Varre .py de produção de dominial/ (excluindo tests/) e falha se ESCOPO_GLOBAL
    aparecer fora de uma allowlist fechada.
(b) Para cada função endurecida no C2, chama sem escopo e assertRaises(TypeError).
"""

import ast
import os
from pathlib import Path
from unittest.mock import Mock

from django.test import TestCase


# Allowlist fechada da seção A do contrato:
# - ImovelDocumentoService (#210)
# - comandos relatorio_cartorios_suspeitos, auditar_divergencia_*, manutencao
# - duplicata conflito_global
ALLOWLIST_ESCOPO_GLOBAL = [
    # managers.py — definição da sentinela ESCOPO_GLOBAL e funções de escopo
    'dominial/managers.py',
    # Services que podem usar ESCOPO_GLOBAL
    'dominial/services/imovel_documento_service.py',
    # Management commands
    'dominial/management/commands/relatorio_cartorios_suspeitos.py',
    'dominial/management/commands/auditar_divergencia_cartorio.py',
    'dominial/management/commands/auditar_divergencia_documento.py',
    'dominial/management/commands/manutencao.py',
    # Duplicata (conflito_global em verificar_duplicata_origem)
    'dominial/services/duplicata_verificacao_service.py',
]


class EscopoGlobalVarreduraTest(TestCase):
    """Teste (a): ESCOPO_GLOBAL só aparece na allowlist fechada."""

    def test_escopo_global_restrito_a_allowlist(self):
        """Varre .py de produção e falha se ESCOPO_GLOBAL aparece fora da allowlist."""
        base = Path(__file__).parent.parent  # dominial/
        violacoes = []

        for py_file in base.rglob('*.py'):
            # Excluir tests/
            if 'tests' in py_file.parts:
                continue

            # Ler e parsear AST
            try:
                source = py_file.read_text(encoding='utf-8')
                tree = ast.parse(source)
            except Exception:
                continue

            # Buscar uso de ESCOPO_GLOBAL
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == 'ESCOPO_GLOBAL':
                    # Verificar se está na allowlist
                    rel_path = str(py_file.relative_to(base.parent))
                    if rel_path not in ALLOWLIST_ESCOPO_GLOBAL:
                        violacoes.append((rel_path, node.lineno))

        if violacoes:
            msg = "ESCOPO_GLOBAL encontrado fora da allowlist:\n"
            for path, line in violacoes:
                msg += f"  {path}:{line}\n"
            msg += f"\nAllowlist permitida:\n  " + "\n  ".join(ALLOWLIST_ESCOPO_GLOBAL)
            self.fail(msg)


class FuncoesEndurecidasTest(TestCase):
    """Teste (b): funções endurecidas no C2 levantam TypeError sem escopo."""

    REGEX_ESCOPO = r'Escopo de documentos|documentos_queryset|keyword-only argument|positional argument'

    def test_hierarquia_utils_identificar_tronco_principal(self):
        """identificar_tronco_principal exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import identificar_tronco_principal
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            identificar_tronco_principal(imovel_mock)

    def test_hierarquia_utils_identificar_documentos_importados(self):
        """identificar_documentos_importados exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import identificar_documentos_importados
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            identificar_documentos_importados(imovel_mock)

    def test_hierarquia_utils_validar_origem_existente(self):
        """_validar_origem_existente exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import _validar_origem_existente
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            _validar_origem_existente('M123', imovel_mock)

    def test_hierarquia_utils_obter_origens_resolvidas(self):
        """obter_origens_resolvidas exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import obter_origens_resolvidas
        documento_mock = Mock()
        documento_mock.lancamentos.all.return_value = []
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            obter_origens_resolvidas(documento_mock)

    def test_hierarquia_utils_processar_origens_para_documentos(self):
        """processar_origens_para_documentos exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import processar_origens_para_documentos
        imovel_mock = Mock()
        lancamento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            processar_origens_para_documentos('M123', imovel_mock, lancamento_mock)

    def test_hierarquia_utils_resolver_documento_por_codigo(self):
        """_resolver_documento_por_codigo exige documentos_queryset posicional."""
        from dominial.utils.hierarquia_utils import _resolver_documento_por_codigo
        cartorio_mock = Mock()
        cartorio_mock.pk = 1
        # Posicional obrigatório — sem o 3º argumento, TypeError
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            _resolver_documento_por_codigo('M123', cartorio_mock)

    def test_arvore_construir_arvore_cadeia_dominial(self):
        """construir_arvore_cadeia_dominial exige documentos_queryset."""
        from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel_mock)

    def test_arvore_identificar_documento_principal(self):
        """_identificar_documento_principal exige documentos_queryset."""
        from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaArvoreService._identificar_documento_principal(imovel_mock)

    def test_arvore_construir_arvore_a_partir_documento(self):
        """_construir_arvore_a_partir_documento exige documentos_queryset."""
        from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
        doc_mock = Mock()
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaArvoreService._construir_arvore_a_partir_documento(
                doc_mock, imovel_mock, False
            )

    def test_arvore_buscar_documentos_pais(self):
        """_buscar_documentos_pais exige documentos_queryset."""
        from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
        doc_mock = Mock()
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaArvoreService._buscar_documentos_pais(
                doc_mock, imovel_mock, False
            )

    def test_hierarquia_service_obter_tronco_principal(self):
        """HierarquiaService.obter_tronco_principal exige escopo."""
        from dominial.services.hierarquia_service import HierarquiaService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaService.obter_tronco_principal(imovel_mock)

    def test_hierarquia_service_obter_troncos_secundarios(self):
        """HierarquiaService.obter_troncos_secundarios exige escopo."""
        from dominial.services.hierarquia_service import HierarquiaService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaService.obter_troncos_secundarios(imovel_mock)

    def test_hierarquia_service_calcular_hierarquia_documentos(self):
        """HierarquiaService.calcular_hierarquia_documentos exige escopo."""
        from dominial.services.hierarquia_service import HierarquiaService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaService.calcular_hierarquia_documentos(imovel_mock)

    def test_hierarquia_service_validar_hierarquia(self):
        """HierarquiaService.validar_hierarquia exige escopo."""
        from dominial.services.hierarquia_service import HierarquiaService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaService.validar_hierarquia(imovel_mock)

    def test_hierarquia_service_construir_arvore_cadeia_dominial(self):
        """HierarquiaService.construir_arvore_cadeia_dominial exige escopo."""
        from dominial.services.hierarquia_service import HierarquiaService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaService.construir_arvore_cadeia_dominial(imovel_mock)

    def test_cadeia_tabela_init(self):
        """CadeiaDominialTabelaService.__init__ exige escopo."""
        from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            CadeiaDominialTabelaService()

    def test_cadeia_tabela_resolver_documento_por_codigo(self):
        """CadeiaDominialTabelaService._resolver_documento_por_codigo exige escopo."""
        from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
        cartorio_mock = Mock()
        cartorio_mock.pk = 1
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            CadeiaDominialTabelaService._resolver_documento_por_codigo('M123', cartorio_mock)

    def test_cadeia_tabela_extrair_origens_disponiveis(self):
        """CadeiaDominialTabelaService.extrair_origens_disponiveis exige escopo."""
        from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
        documento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            CadeiaDominialTabelaService.extrair_origens_disponiveis(documento_mock)

    def test_cadeia_completa_init(self):
        """CadeiaCompletaService.__init__ exige escopo."""
        from dominial.services.cadeia_completa_service import CadeiaCompletaService
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            CadeiaCompletaService()

    def test_cadeia_completa_resolver_documento_por_codigo(self):
        """CadeiaCompletaService._resolver_documento_por_codigo exige escopo."""
        from dominial.services.cadeia_completa_service import CadeiaCompletaService
        cartorio_mock = Mock()
        cartorio_mock.pk = 1
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            CadeiaCompletaService._resolver_documento_por_codigo('M123', cartorio_mock)

    def test_duplicata_verificar_duplicata_origem(self):
        """DuplicataVerificacaoService.verificar_duplicata_origem exige escopo."""
        from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            DuplicataVerificacaoService.verificar_duplicata_origem('M123', 1, 1)

    def test_duplicata_calcular_documentos_importaveis(self):
        """DuplicataVerificacaoService.calcular_documentos_importaveis exige escopo."""
        from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
        documento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            DuplicataVerificacaoService.calcular_documentos_importaveis(documento_mock)

    def test_duplicata_obter_cadeia_dominial_origem(self):
        """DuplicataVerificacaoService.obter_cadeia_dominial_origem exige escopo."""
        from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
        documento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            DuplicataVerificacaoService.obter_cadeia_dominial_origem(documento_mock)

    def test_duplicata_resolver_documento(self):
        """DuplicataVerificacaoService._resolver_documento exige escopo."""
        from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            DuplicataVerificacaoService._resolver_documento('M123', 1)

    def test_duplicata_verificar_performance_consulta(self):
        """DuplicataVerificacaoService.verificar_performance_consulta exige escopo."""
        from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
        documento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            DuplicataVerificacaoService.verificar_performance_consulta(documento_mock)

    def test_status_cadeia_status_por_imovel(self):
        """StatusCadeiaService.status_por_imovel exige escopo."""
        from dominial.services.status_cadeia_service import StatusCadeiaService
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            StatusCadeiaService.status_por_imovel(1)

    def test_hierarquia_origem_processar_origens_identificadas(self):
        """HierarquiaOrigemService.processar_origens_identificadas exige escopo."""
        from dominial.services.hierarquia_origem_service import HierarquiaOrigemService
        imovel_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaOrigemService.processar_origens_identificadas(imovel_mock)

    def test_hierarquia_origem_resolver_documento(self):
        """HierarquiaOrigemService._resolver_documento exige escopo."""
        from dominial.services.hierarquia_origem_service import HierarquiaOrigemService
        cartorio_mock = Mock()
        cartorio_mock.pk = 1
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            HierarquiaOrigemService._resolver_documento('matricula', '123', cartorio_mock)

    def test_hierarquia_utils_contar_origens_restritas(self):
        """contar_origens_restritas exige documentos_queryset."""
        from dominial.utils.hierarquia_utils import contar_origens_restritas
        documento_mock = Mock()
        with self.assertRaisesRegex(TypeError, self.REGEX_ESCOPO):
            contar_origens_restritas(documento_mock)
