"""
Unit tests for LancamentoCriacaoService.

Tests the creation and update of lancamentos (property transactions).
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from django.http import QueryDict

from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.models import Lancamento, LancamentoTipo
from .factories import (
    DocumentoFactory,
    LancamentoFactory,
    LancamentoTipoFactory,
    CartoriosFactory,
    PessoasFactory,
    ImovelFactory,
    TIsFactory,
)


@pytest.mark.unit
@pytest.mark.service
class TestLancamentoCriacaoServiceBasicMethods:
    """Test basic helper methods of LancamentoCriacaoService."""

    def test_criar_lancamento_basico_registro(self, db):
        """Test creating basic registro lancamento."""
        # Arrange
        documento = DocumentoFactory()
        tipo_lanc = LancamentoTipoFactory.registro()
        cartorio = CartoriosFactory()

        dados_lancamento = {
            'numero_lancamento': 'R-1',
            'data': date(2024, 1, 15),
            'observacoes': 'Test observation',
            'forma': 'Escritura Pública',
            'descricao': '',
            'titulo': 'Compra e Venda',
            'livro_origem': 'L01',
            'folha_origem': '100',
            'cartorio_origem': cartorio,
            'area': '1500.50',
            'origem': 'T-100'
        }

        # Act
        lancamento = LancamentoCriacaoService._criar_lancamento_basico(
            documento, dados_lancamento, tipo_lanc
        )

        # Assert
        assert lancamento is not None
        assert lancamento.documento == documento
        assert lancamento.tipo == tipo_lanc
        assert lancamento.numero_lancamento == 'R-1'
        assert lancamento.data == date(2024, 1, 15)
        assert lancamento.observacoes == 'Test observation'
        assert lancamento.titulo == 'Compra e Venda'
        assert lancamento.livro_origem == 'L01'
        assert lancamento.folha_origem == '100'
        assert lancamento.area == 1500.50
        assert lancamento.origem == 'T-100'

    def test_criar_lancamento_basico_averbacao(self, db):
        """Test creating basic averbação lancamento."""
        # Arrange
        documento = DocumentoFactory()
        tipo_lanc = LancamentoTipoFactory.averbacao()

        dados_lancamento = {
            'numero_lancamento': 'AV-5',
            'data': date(2024, 2, 20),
            'observacoes': 'Averbação test',
            'forma': '',
            'descricao': 'Mudança de estado civil',
            'titulo': '',
            'livro_origem': '',
            'folha_origem': '',
            'cartorio_origem': None,
            'area': '',
            'origem': ''
        }

        # Act
        lancamento = LancamentoCriacaoService._criar_lancamento_basico(
            documento, dados_lancamento, tipo_lanc
        )

        # Assert
        assert lancamento.numero_lancamento == 'AV-5'
        assert lancamento.descricao == 'Mudança de estado civil'
        assert lancamento.titulo == ''
        assert lancamento.area is None  # Empty string should be None

    def test_criar_lancamento_basico_area_handling(self, db):
        """Test proper handling of area field (empty string vs number)."""
        # Arrange
        documento = DocumentoFactory()
        tipo_lanc = LancamentoTipoFactory.registro()

        # Test with empty area
        dados_empty = {
            'numero_lancamento': 'R-1',
            'data': date(2024, 1, 15),
            'observacoes': '',
            'forma': '',
            'descricao': '',
            'titulo': 'Test',
            'livro_origem': '',
            'folha_origem': '',
            'cartorio_origem': None,
            'area': '',  # Empty string
            'origem': ''
        }

        # Act
        lanc1 = LancamentoCriacaoService._criar_lancamento_basico(
            documento, dados_empty, tipo_lanc
        )

        # Assert
        assert lanc1.area is None

        # Test with valid area
        dados_valid = dados_empty.copy()
        dados_valid['area'] = '2500.75'
        lanc2 = LancamentoCriacaoService._criar_lancamento_basico(
            DocumentoFactory(), dados_valid, tipo_lanc
        )

        assert lanc2.area == 2500.75

    def test_aplicar_campos_documento_livro_folha(self, db):
        """Test applying livro and folha to document."""
        # Arrange
        lancamento = LancamentoFactory()
        documento = lancamento.documento

        # Original values
        documento.livro = 'L00'
        documento.folha = '000'
        documento.save()

        dados_lancamento = {
            'livro_documento': 'L05',
            'folha_documento': '125',
            'livro_origem': '',
            'folha_origem': ''
        }

        # Act
        result = LancamentoCriacaoService._aplicar_campos_documento(
            lancamento, dados_lancamento
        )

        # Assert
        assert result is True
        documento.refresh_from_db()
        assert documento.livro == 'L05'
        assert documento.folha == '125'

    def test_aplicar_campos_documento_heranca_origem(self, db):
        """Test inheriting livro/folha from origem fields."""
        # Arrange
        lancamento = LancamentoFactory()
        documento = lancamento.documento

        dados_lancamento = {
            'livro_documento': '',  # Empty
            'folha_documento': '',  # Empty
            'livro_origem': 'L10',  # Should be inherited
            'folha_origem': '200'   # Should be inherited
        }

        # Act
        result = LancamentoCriacaoService._aplicar_campos_documento(
            lancamento, dados_lancamento
        )

        # Assert
        assert result is True
        documento.refresh_from_db()
        assert documento.livro == 'L10'
        assert documento.folha == '200'

    def test_aplicar_campos_documento_prioridade(self, db):
        """Test that livro_documento takes priority over livro_origem."""
        # Arrange
        lancamento = LancamentoFactory()
        documento = lancamento.documento

        dados_lancamento = {
            'livro_documento': 'L99',  # Should win
            'folha_documento': '999',  # Should win
            'livro_origem': 'L10',
            'folha_origem': '100'
        }

        # Act
        result = LancamentoCriacaoService._aplicar_campos_documento(
            lancamento, dados_lancamento
        )

        # Assert
        assert result is True
        documento.refresh_from_db()
        assert documento.livro == 'L99'
        assert documento.folha == '999'

    def test_aplicar_campos_documento_no_changes(self, db):
        """Test when no campos need to be applied."""
        # Arrange
        lancamento = LancamentoFactory()

        dados_lancamento = {
            'livro_documento': '',
            'folha_documento': '',
            'livro_origem': '',
            'folha_origem': ''
        }

        # Act
        result = LancamentoCriacaoService._aplicar_campos_documento(
            lancamento, dados_lancamento
        )

        # Assert
        assert result is False  # No changes made


@pytest.mark.unit
@pytest.mark.service
@pytest.mark.integration
class TestLancamentoCriacaoServiceIntegration:
    """Integration tests for LancamentoCriacaoService with mocked requests."""

    def create_mock_request(self, post_data):
        """Helper to create a mock Django request object with real QueryDict."""
        request = Mock()

        # Use a real QueryDict for accurate Django behavior
        q_dict = QueryDict('', mutable=True)

        # Properly handle lists in POST data for QueryDict
        for key, value in post_data.items():
            if isinstance(value, list):
                # For list values, add each item separately
                for item in value:
                    q_dict.appendlist(key, item)
            else:
                # For single values, use update
                q_dict[key] = value

        request.POST = q_dict
        # No need to mock getlist - QueryDict provides it natively
        return request

    @patch('dominial.services.lancamento_criacao_service.LancamentoDuplicataService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoPessoaService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoOrigemService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoCamposService')
    @patch('dominial.services.lancamento_criacao_service.RegraPetreaService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoFormService')
    def test_criar_lancamento_completo_registro_success(
        self, mock_form_service, mock_regra, mock_campos,
        mock_origem, mock_pessoa, mock_duplicata, db
    ):
        """Test successful creation of complete registro lancamento."""
        # Arrange
        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)
        tipo_lanc = LancamentoTipoFactory.registro()
        transmitente = PessoasFactory()
        adquirente = PessoasFactory()

        post_data = {
            'tipo_lancamento': str(tipo_lanc.id),
            'numero_lancamento_simples': '1',
            'numero_lancamento': 'R-1',
            'data': '2024-01-15',
            'titulo': 'Compra e Venda',
            'observacoes': 'Test',
            'cartorio_origem[]': [],
            'cartorio_origem_nome[]': [],
            'origem_completa[]': [],
            'transmitente_nome[]': [transmitente.nome],
            'transmitente[]': [str(transmitente.id)],
            'adquirente_nome[]': [adquirente.nome],
            'adquirente[]': [str(adquirente.id)],
        }

        request = self.create_mock_request(post_data)

        # Mock service responses
        mock_form_service.processar_dados_lancamento.return_value = {
            'numero_lancamento': 'R-1',
            'data': date(2024, 1, 15),
            'observacoes': 'Test',
            'forma': '',
            'descricao': '',
            'titulo': 'Compra e Venda',
            'livro_origem': '',
            'folha_origem': '',
            'cartorio_origem': None,
            'area': '',
            'origem': ''
        }

        mock_duplicata.verificar_duplicata_antes_criacao.return_value = {
            'tem_duplicata': False,
            'mensagem': ''
        }

        mock_origem.processar_origens_automaticas.return_value = "Origens processadas"

        # Act
        result, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, ti, imovel, documento
        )

        # Assert
        assert result is not None
        assert isinstance(result, Lancamento)
        assert result.documento == documento
        assert result.tipo == tipo_lanc
        assert mensagem == "Origens processadas"

        # Verify services were called
        mock_form_service.processar_dados_lancamento.assert_called_once()
        mock_duplicata.verificar_duplicata_antes_criacao.assert_called_once()
        mock_origem.processar_origens_automaticas.assert_called_once()
        mock_pessoa.processar_pessoas_lancamento.assert_called()

    def test_criar_lancamento_completo_missing_tipo(self, db):
        """Test error when tipo_lancamento is missing."""
        # Arrange
        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)

        post_data = {}  # No tipo_lancamento
        request = self.create_mock_request(post_data)

        # Act
        result, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, ti, imovel, documento
        )

        # Assert
        assert result is None
        assert "obrigatório" in mensagem.lower()

    def test_criar_lancamento_completo_invalid_tipo(self, db):
        """Test error when tipo_lancamento doesn't exist."""
        # Arrange
        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)

        post_data = {'tipo_lancamento': '99999'}  # Non-existent ID
        request = self.create_mock_request(post_data)

        # Act
        result, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, ti, imovel, documento
        )

        # Assert
        assert result is None
        assert "não encontrado" in mensagem.lower()

    def test_criar_lancamento_completo_missing_numero_simples(self, db):
        """Test error when numero_simples is missing for registro."""
        # Arrange
        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)
        tipo_lanc = LancamentoTipoFactory.registro()

        post_data = {
            'tipo_lancamento': str(tipo_lanc.id),
            'numero_lancamento_simples': '',  # Empty
        }
        request = self.create_mock_request(post_data)

        # Act
        result, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, ti, imovel, documento
        )

        # Assert
        assert result is None
        assert "obrigatório" in mensagem.lower()

    @patch('dominial.services.lancamento_criacao_service.LancamentoDuplicataService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoFormService')
    def test_criar_lancamento_completo_duplicata_found(
        self, mock_form_service, mock_duplicata, db
    ):
        """Test handling when duplicata is found."""
        # Arrange
        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)
        tipo_lanc = LancamentoTipoFactory.registro()

        post_data = {
            'tipo_lancamento': str(tipo_lanc.id),
            'numero_lancamento_simples': '1',
            'cartorio_origem[]': [],
            'cartorio_origem_nome[]': [],
            'origem_completa[]': [],
        }
        request = self.create_mock_request(post_data)

        mock_form_service.processar_dados_lancamento.return_value = {
            'numero_lancamento': 'R-1',
            'data': date(2024, 1, 15),
            'observacoes': '',
            'forma': '',
            'descricao': '',
            'titulo': '',
            'livro_origem': '',
            'folha_origem': '',
            'cartorio_origem': None,
            'area': '',
            'origem': ''
        }

        mock_duplicata.verificar_duplicata_antes_criacao.return_value = {
            'tem_duplicata': True,
            'mensagem': 'Duplicata encontrada',
            'lancamento_similar': {}
        }

        # Act
        result, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, ti, imovel, documento
        )

        # Assert
        assert result is not None
        assert result['tipo'] == 'duplicata_encontrada'
        assert 'duplicata_info' in result
        assert mensagem == 'Duplicata encontrada'

    @patch('dominial.services.lancamento_criacao_service.LancamentoCamposService')
    @patch('dominial.services.lancamento_criacao_service.LancamentoPessoaService')
    def test_atualizar_lancamento_completo_success(
        self, mock_pessoa, mock_campos, db
    ):
        """Test successful update of lancamento."""
        # Arrange
        lancamento = LancamentoFactory.registro()
        imovel = lancamento.documento.imovel
        tipo_lanc = lancamento.tipo

        post_data = {
            'tipo_lancamento': str(tipo_lanc.id),
            'numero_lancamento_simples': '2',
            'numero_lancamento': 'R-2',
            'data': '2024-02-20',
            'observacoes': 'Updated observation',
            'origem_completa[]': [],
        }
        request = self.create_mock_request(post_data)

        # Act
        success, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, lancamento, imovel
        )

        # Assert
        assert success is True
        lancamento.refresh_from_db()
        assert lancamento.numero_lancamento == 'R-2'
        assert lancamento.observacoes == 'Updated observation'


@pytest.mark.unit
@pytest.mark.service
class TestLancamentoCriacaoServiceEdgeCases:
    """Test edge cases and error handling."""

    def test_criar_lancamento_basico_with_none_values(self, db):
        """Test creating lancamento with None values."""
        # Arrange
        documento = DocumentoFactory()
        tipo_lanc = LancamentoTipoFactory.registro()

        dados_lancamento = {
            'numero_lancamento': 'R-1',
            'data': date(2024, 1, 15),
            'observacoes': None,  # None value
            'forma': None,
            'descricao': None,
            'titulo': None,
            'livro_origem': None,
            'folha_origem': None,
            'cartorio_origem': None,
            'area': None,
            'origem': None
        }

        # Act
        lancamento = LancamentoCriacaoService._criar_lancamento_basico(
            documento, dados_lancamento, tipo_lanc
        )

        # Assert
        assert lancamento is not None
        # Should handle None values gracefully

    def test_aplicar_campos_documento_whitespace_handling(self, db):
        """Test handling of whitespace in livro/folha fields."""
        # Arrange
        lancamento = LancamentoFactory()
        documento = lancamento.documento

        dados_lancamento = {
            'livro_documento': '  L05  ',  # Whitespace
            'folha_documento': '  125  ',  # Whitespace
            'livro_origem': '',
            'folha_origem': ''
        }

        # Act
        result = LancamentoCriacaoService._aplicar_campos_documento(
            lancamento, dados_lancamento
        )

        # Assert
        assert result is True
        documento.refresh_from_db()
        assert documento.livro == 'L05'  # Trimmed
        assert documento.folha == '125'  # Trimmed
