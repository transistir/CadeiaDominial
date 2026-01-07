# Forms package

# Importar todos os forms para manter compatibilidade
from .tis_forms import TIsForm
from .imovel_forms import ImovelForm

# Exportar todos os forms para uso externo
__all__ = [
    'TIsForm',
    'ImovelForm',
] 