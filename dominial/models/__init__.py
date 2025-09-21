# Models package

# Importar todos os models para manter compatibilidade
from .tis_models import TIs, TerraIndigenaReferencia, TIs_Imovel
from .pessoa_models import Pessoas
from .imovel_models import Imovel, Cartorios, ImportacaoCartorios
from .documento_models import Documento, DocumentoTipo
from .lancamento_models import Lancamento, LancamentoTipo, LancamentoPessoa, OrigemFimCadeia, FimCadeia
from .alteracao_models import Alteracoes, AlteracoesTipo, RegistroTipo, AverbacoesTipo
from .documento_importado_models import DocumentoImportado

# Exportar todos os models para uso externo
__all__ = [
    'TIs', 'TerraIndigenaReferencia', 'TIs_Imovel',
    'Pessoas',
    'Imovel', 'Cartorios', 'ImportacaoCartorios',
    'Documento', 'DocumentoTipo',
    'Lancamento', 'LancamentoTipo', 'LancamentoPessoa', 'OrigemFimCadeia', 'FimCadeia',
    'Alteracoes', 'AlteracoesTipo', 'RegistroTipo', 'AverbacoesTipo',
    'DocumentoImportado',
] 