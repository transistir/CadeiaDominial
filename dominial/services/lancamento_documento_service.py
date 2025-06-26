"""
Service para operações com documentos de lançamento
"""
from ..models import Documento, DocumentoTipo, Cartorios
from django.shortcuts import get_object_or_404

class LancamentoDocumentoService:
    @staticmethod
    def obter_documento_ativo(imovel, documento_id=None):
        if documento_id:
            return get_object_or_404(Documento, id=documento_id, imovel=imovel)
        else:
            return Documento.objects.filter(imovel=imovel).order_by('-data', '-id').first()

    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        try:
            tipo_matricula = DocumentoTipo.objects.get(tipo='matricula')
            documento = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_matricula,
                numero=imovel.matricula,
                data=imovel.data_cadastro,
                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                livro='1',
                folha='1',
                origem='Matrícula atual do imóvel',
                observacoes='Documento criado automaticamente ao iniciar a cadeia dominial'
            )
            return documento, f'Documento de matrícula "{imovel.matricula}" criado automaticamente.'
        except Exception as e:
            raise Exception(f'Erro ao criar documento de matrícula: {str(e)}') 