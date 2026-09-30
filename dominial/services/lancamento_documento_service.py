"""
Service especializado para operações com documentos relacionados a lançamentos
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import Documento
from ..utils.documento_identidade_utils import (
    PREFIXOS_POR_TIPO,
    normalizar_numero_documento,
)


class LancamentoDocumentoService:
    """
    Service para operações com documentos relacionados a lançamentos
    """
    
    @staticmethod
    def obter_documento_ativo(imovel, documento_id=None):
        """
        Obtém o documento ativo do imóvel
        
        Args:
            imovel: Imóvel para buscar o documento
            documento_id: ID específico do documento (opcional)
            
        Returns:
            Documento: Documento ativo ou None se não encontrado
        """
        if documento_id:
            return Documento.objects.get(id=documento_id, imovel=imovel)
        # Retorna o documento mais recente como ativo
        return imovel.documentos.order_by('-data', '-id').first()
    
    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        """Cria automaticamente o documento principal do imóvel.

        O documento é do tipo declarado em ``Imovel.tipo_documento_principal``
        (matrícula ou transcrição); se o tipo estiver ausente ou for inválido,
        cai no default ``'matricula'``. ``Imovel.matricula`` é o campo
        genérico do número — o prefixo (``M``/``T``) é acrescentado aqui
        quando necessário, usando ``normalizar_numero_documento`` para
        evitar duplicação e validar contradições.

        Args:
            imovel: Imóvel para criar o documento

        Returns:
            Documento: Documento principal criado (matrícula ou transcrição)

        Raises:
            ValidationError: quando ``imovel.cartorio_id`` está ausente (#114).
            ValueError: quando o número é vazio, contradiz o prefixo do tipo
                ou contém apenas o prefixo. A exceção sobe sem captura —
                callers que precisam tratar devem envolvê-la em ``try``.
        """
        from ..models import DocumentoTipo

        # Guard #114: ler SOMENTE ``cartorio_id`` — nunca ``imovel.cartorio``
        # (RelatedObjectDoesNotExist herda de AttributeError e seria engolida
        # por getattr/hasattr).
        if not imovel.cartorio_id:
            raise ValidationError(
                'Cartório é obrigatório para criar o documento principal do imóvel.'
            )

        # Tipo do documento: se o declarado estiver em PREFIXOS_POR_TIPO,
        # usa-o; senão, cai no default 'matricula'.
        tipo_declarado = imovel.tipo_documento_principal
        tipo = tipo_declarado if tipo_declarado in PREFIXOS_POR_TIPO else 'matricula'

        # Normaliza o número (strip + validação de prefixo) e acrescenta
        # o prefixo do tipo. ValueError de número vazio, prefixo
        # contraditório ou só prefixo sobem sem captura.
        numero_normalizado = normalizar_numero_documento(imovel.matricula, tipo)
        numero_documento = f'{PREFIXOS_POR_TIPO[tipo]}{numero_normalizado}'

        tipo_obj = DocumentoTipo.objects.get_or_create(tipo=tipo)[0]
        rotulo = tipo_obj.get_tipo_display()

        return Documento.objects.create(
            imovel=imovel,
            tipo=tipo_obj,
            numero=numero_documento,
            data=timezone.localdate(),
            data_presumida=True,
            cartorio_id=imovel.cartorio_id,
            livro='0',  # Valor padrão, será atualizado pelo primeiro lançamento
            folha='0',  # Valor padrão, será atualizado pelo primeiro lançamento
            origem=f'{rotulo} atual do imóvel',
            observacoes=(
                f'Documento de {rotulo.lower()} criado automaticamente '
                'para iniciar a cadeia dominial'
            ),
        )
    
    @staticmethod
    def obter_documentos_por_imovel(imovel):
        """
        Obtém todos os documentos de um imóvel
        
        Args:
            imovel: Imóvel para buscar os documentos
            
        Returns:
            QuerySet: Documentos do imóvel
        """
        return imovel.documentos.all().order_by('-data', 'tipo', 'numero', '-id')