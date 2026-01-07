# Services package

# Importar todos os services para manter compatibilidade
from .hierarquia_service import HierarquiaService
from .documento_service import DocumentoService
from .lancamento_service import LancamentoService
from .cartorio_verificacao_service import CartorioVerificacaoService

# Exportar todos os services para uso externo
__all__ = [
    'HierarquiaService',
    'DocumentoService',
    'LancamentoService',
    'CartorioVerificacaoService',
] 