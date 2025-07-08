# Views package - Imports explícitos das views organizadas por domínio

# Views de Terras Indígenas
from .tis_views import (
    home,
    tis_form,
    tis_detail,
    tis_delete,
    imoveis,
    imovel_detail,
    imovel_delete,
)

# Views de Imóveis
from .imovel_views import (
    imovel_form,
)

# Views de Documentos
from .documento_views import (
    novo_documento,
    documento_lancamentos,
    selecionar_documento_lancamento,
    editar_documento,
    criar_documento_automatico,
)

# Views de Lançamentos
from .lancamento_views import (
    novo_lancamento,
    editar_lancamento,
    excluir_lancamento,
    lancamento_detail,
)

# Views de Cadeia Dominial
from .cadeia_dominial_views import (
    cadeia_dominial,
    cadeia_dominial_arvore,
    tronco_principal,
    cadeia_dominial_dados,
    cadeia_dominial_tabela,
    cadeia_dominial_d3,
)

# Views de API/AJAX
from .api_views import (
    buscar_cidades,
    buscar_cartorios,
    verificar_cartorios_estado,
    importar_cartorios_estado,
    criar_cartorio,
    cartorios,
    pessoas,
    alteracoes,
    lancamentos,
    escolher_origem_documento,
    escolher_origem_lancamento,
    get_cadeia_dominial_atualizada,
)

# Views de Autocomplete
from .autocomplete_views import (
    pessoa_autocomplete,
    cartorio_autocomplete,
    cartorio_imoveis_autocomplete,
)

# Exportar todas as views para uso externo
__all__ = [
    # Views de Terras Indígenas
    'home',
    'tis_form',
    'tis_detail',
    'tis_delete',
    'imoveis',
    'imovel_detail',
    'imovel_delete',
    
    # Views de Imóveis
    'imovel_form',
    
    # Views de Documentos
    'novo_documento',
    'documento_lancamentos',
    'selecionar_documento_lancamento',
    'editar_documento',
    'criar_documento_automatico',
    
    # Views de Lançamentos
    'novo_lancamento',
    'editar_lancamento',
    'excluir_lancamento',
    'lancamento_detail',
    
    # Views de Cadeia Dominial
    'cadeia_dominial',
    'cadeia_dominial_arvore',
    'tronco_principal',
    'cadeia_dominial_dados',
    'cadeia_dominial_tabela',
    'cadeia_dominial_d3',
    
    # Views de API/AJAX
    'buscar_cidades',
    'buscar_cartorios',
    'verificar_cartorios_estado',
    'importar_cartorios_estado',
    'criar_cartorio',
    'cartorios',
    'pessoas',
    'alteracoes',
    'lancamentos',
    'escolher_origem_documento',
    'escolher_origem_lancamento',
    'get_cadeia_dominial_atualizada',
    
    # Views de Autocomplete
    'pessoa_autocomplete',
    'cartorio_autocomplete',
    'cartorio_imoveis_autocomplete',
] 