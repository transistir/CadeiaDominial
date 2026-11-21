# Utils package

# Importar todos os utilitários para manter compatibilidade
from .documento_identidade_utils import DocumentoIdentidade, normalizar_numero_documento
from .formatacao_utils import (
    abreviar_cartorio,
    formatar_area_ha,
    formatar_cpf,
    formatar_telefone,
    formatar_valor_monetario,
    normalizar_texto_opcional,
)
from .hierarquia_utils import (
    ajustar_nivel_para_nova_conexao,
    calcular_niveis_hierarquicos_otimizada,
    identificar_tronco_principal,
    identificar_troncos_secundarios,
)
from .permissoes_utils import usuario_pode_criar_ti
from .validacao_utils import validar_cpf, validar_matricula, validar_sncr

# Exportar todos os utilitários para uso externo
__all__ = [
    'DocumentoIdentidade',
    'abreviar_cartorio',
    'ajustar_nivel_para_nova_conexao',
    'calcular_niveis_hierarquicos_otimizada',
    'formatar_area_ha',
    'formatar_cpf',
    'formatar_telefone',
    'formatar_valor_monetario',
    'identificar_tronco_principal',
    'identificar_troncos_secundarios',
    'normalizar_numero_documento',
    'normalizar_texto_opcional',
    'usuario_pode_criar_ti',
    'validar_cpf',
    'validar_matricula',
    'validar_sncr',
]