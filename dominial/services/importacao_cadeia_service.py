"""
Service para importação de cadeias dominiais.
Importa documentos de outras cadeias dominiais para o imóvel atual.
"""

from django.db import transaction
from django.contrib.auth.models import User
from typing import Dict, List, Any
from ..models import Documento, DocumentoImportado, Imovel


class ImportacaoCadeiaService:
    """
    Service responsável por importar cadeias dominiais de outros imóveis.
    """
    
    @staticmethod
    def importar_cadeia_dominial(
        imovel_destino_id: int,
        documento_origem_id: int,
        documentos_importaveis_ids: List[int],
        usuario_id: int
    ) -> Dict[str, Any]:
        """
        Importa uma cadeia dominial para o imóvel destino.
        
        Args:
            imovel_destino_id: ID do imóvel que receberá a importação
            documento_origem_id: ID do documento origem
            documentos_importaveis_ids: Lista de IDs dos documentos a importar
            usuario_id: ID do usuário que está fazendo a importação
            
        Returns:
            Dict com resultado da importação
        """
        try:
            with transaction.atomic():
                # Verificar se o imóvel destino existe
                imovel_destino = Imovel.objects.get(id=imovel_destino_id)
                
                # Verificar se o documento origem existe
                documento_origem = Documento.objects.get(id=documento_origem_id)
                
                # Verificar se o usuário existe
                usuario = User.objects.get(id=usuario_id)
                
                documentos_importados = []
                erros = []
                
                # Importar cada documento da lista
                for doc_id in documentos_importaveis_ids:
                    try:
                        documento = Documento.objects.get(id=doc_id)

                        # Verificar se já não foi importado (de qualquer propriedade)
                        # Correção: verifica apenas pelo documento, não pelo imovel_origem
                        # Isso previne duplicatas mesmo quando o documento é alcançado através
                        # de diferentes caminhos na cadeia (propriedades diferentes)
                        if DocumentoImportado.objects.filter(
                            documento=documento
                        ).exists():
                            erros.append(f"Documento {documento.numero} já foi importado")
                            continue

                        # Marcar documento como importado, keeping it in its original imóvel
                        # The document stays in place - we just record the import relationship
                        # This preserves the source property's chain integrity
                        documento_importado = ImportacaoCadeiaService.marcar_documento_importado(
                            documento=documento,
                            imovel_origem=documento.imovel,
                            imovel_destino=imovel_destino,
                            importado_por=usuario
                        )
                        
                        documentos_importados.append({
                            'id': documento.id,
                            'numero': documento.numero,
                            'tipo': documento.tipo.tipo,
                            'data_importacao': documento_importado.data_importacao
                        })
                        
                    except Documento.DoesNotExist:
                        erros.append(f"Documento com ID {doc_id} não encontrado")
                    except Exception as e:
                        erros.append(f"Erro ao importar documento {doc_id}: {str(e)}")
                
                # Se todos os documentos já foram importados, considerar como sucesso
                if len(documentos_importados) == 0 and len(erros) > 0 and all('já foi importado' in erro for erro in erros):
                    return {
                        'sucesso': True,
                        'documentos_importados': documentos_importados,
                        'total_importados': len(documentos_importados),
                        'mensagem': 'Todos os documentos já foram importados anteriormente',
                        'imovel_destino': {
                            'id': imovel_destino.id,
                            'matricula': imovel_destino.matricula
                        }
                    }
                else:
                    # Considerar sucesso se pelo menos um documento foi importado
                    # ou se todos os erros são apenas "já foi importado"
                    sucesso = len(documentos_importados) > 0 or all('já foi importado' in erro for erro in erros)
                    
                    return {
                        'sucesso': sucesso,
                        'documentos_importados': documentos_importados,
                        'total_importados': len(documentos_importados),
                        'erros': erros,
                        'mensagem': f'Importação concluída: {len(documentos_importados)} documentos importados' if sucesso else 'Falha na importação',
                        'imovel_destino': {
                            'id': imovel_destino.id,
                            'matricula': imovel_destino.matricula
                        }
                    }
                
        except Imovel.DoesNotExist:
            return {
                'sucesso': False,
                'erro': f'Imóvel com ID {imovel_destino_id} não encontrado'
            }
        except Documento.DoesNotExist:
            return {
                'sucesso': False,
                'erro': f'Documento origem com ID {documento_origem_id} não encontrado'
            }
        except User.DoesNotExist:
            return {
                'sucesso': False,
                'erro': f'Usuário com ID {usuario_id} não encontrado'
            }
        except Exception as e:
            return {
                'sucesso': False,
                'erro': f'Erro inesperado: {str(e)}'
            }
    
    @staticmethod
    def marcar_documento_importado(
        documento: Documento,
        imovel_origem: Imovel,
        imovel_destino: Imovel,
        importado_por: User
    ) -> DocumentoImportado:
        """
        Marca um documento como importado.

        Args:
            documento: Documento que foi importado
            imovel_origem: Imóvel de origem do documento
            imovel_destino: Imóvel de destino da importação
            importado_por: Usuário que fez a importação

        Returns:
            Instância do DocumentoImportado criado
        """
        documento_importado, created = DocumentoImportado.objects.get_or_create(
            documento=documento,
            imovel_origem=imovel_origem,
            defaults={
                'imovel_destino': imovel_destino,
                'importado_por': importado_por
            }
        )

        return documento_importado
    
    @staticmethod
    def verificar_documentos_importados(imovel_id: int) -> List[Dict[str, Any]]:
        """
        Verifica quais documentos foram importados para um imóvel.

        Args:
            imovel_id: ID do imóvel (destino da importação)

        Returns:
            Lista de documentos importados
        """
        documentos_importados = DocumentoImportado.objects.filter(
            imovel_destino_id=imovel_id
        ).select_related('documento', 'documento__tipo', 'documento__cartorio', 'imovel_origem')

        resultado = []
        for doc_importado in documentos_importados:
            resultado.append({
                'id': doc_importado.documento.id,
                'numero': doc_importado.documento.numero,
                'tipo': doc_importado.documento.tipo.tipo,
                'data_importacao': doc_importado.data_importacao,
                'importado_por': doc_importado.importado_por.username if doc_importado.importado_por else None,
                'imovel_origem': {
                    'id': doc_importado.imovel_origem.id,
                    'matricula': doc_importado.imovel_origem.matricula
                }
            })

        return resultado
    
    @staticmethod
    def desfazer_importacao(documento_importado_id: int, usuario_id: int) -> Dict[str, Any]:
        """
        Desfaz uma importação específica.
        
        Args:
            documento_importado_id: ID do registro de importação
            usuario_id: ID do usuário que está desfazendo
            
        Returns:
            Dict com resultado da operação
        """
        try:
            with transaction.atomic():
                documento_importado = DocumentoImportado.objects.get(id=documento_importado_id)
                
                # Verificar se o usuário tem permissão (pode ser expandido)
                if documento_importado.importado_por and documento_importado.importado_por.id != usuario_id:
                    return {
                        'sucesso': False,
                        'erro': 'Usuário não tem permissão para desfazer esta importação'
                    }
                
                # Remover o registro de importação
                documento_importado.delete()
                
                return {
                    'sucesso': True,
                    'mensagem': f'Importação do documento {documento_importado.documento.numero} desfeita com sucesso'
                }
                
        except DocumentoImportado.DoesNotExist:
            return {
                'sucesso': False,
                'erro': f'Registro de importação com ID {documento_importado_id} não encontrado'
            }
        except Exception as e:
            return {
                'sucesso': False,
                'erro': f'Erro ao desfazer importação: {str(e)}'
            } 