"""
Service para integração da verificação de duplicatas com o processo de criação de lançamentos
"""

import logging
from .duplicata_verificacao_service import DuplicataVerificacaoService
from .importacao_cadeia_service import ImportacaoCadeiaService
from ..models import Documento, Cartorios

logger = logging.getLogger(__name__)


class LancamentoDuplicataService:
    """
    Service para integrar verificação de duplicatas ao processo de criação de lançamentos
    """
    
    @staticmethod
    def verificar_duplicata_antes_criacao(request, documento_ativo):
        """
        Verifica se há duplicatas antes de criar um lançamento
        
        Args:
            request: HttpRequest com dados do formulário
            documento_ativo: Documento ativo do imóvel
            
        Returns:
            dict: Resultado da verificação com informações sobre duplicatas encontradas
        """
        # Obter dados do formulário (campos são enviados como arrays)
        origens = request.POST.getlist('origem_completa[]')
        cartorios_origem = request.POST.getlist('cartorio_origem[]')
        
        logger.debug(f"DUPLICATA: Origens recebidas: {origens}")
        logger.debug(f"DUPLICATA: Cartórios origem recebidos: {cartorios_origem}")
        logger.debug(f"DUPLICATA: Todos os campos POST: {list(request.POST.keys())}")
        
        # Verificar duplicatas em TODAS as origens, não apenas a primeira
        padroes_fim_cadeia = [
            'FIM_CADEIA',
            'Destacamento Público:',
            'Outra:',
            'Sem Origem:'
        ]
        
        for i, origem in enumerate(origens):
            origem = origem.strip() if origem else ''
            cartorio_origem_id = cartorios_origem[i] if i < len(cartorios_origem) and cartorios_origem[i] else None
            
            logger.debug(f"DUPLICATA: Verificando origem {i}: '{origem}'")
            logger.debug(f"DUPLICATA: Cartório origem ID {i}: '{cartorio_origem_id}'")
            
            if not origem:
                continue
                
            # Verificar se é origem de fim de cadeia
            is_fim_cadeia = any(padrao in origem for padrao in padroes_fim_cadeia)
            
            if is_fim_cadeia:
                # Para origens de fim de cadeia, não verificar duplicatas
                logger.debug(f"DUPLICATA: Origem {i} é fim de cadeia, pulando verificação")
                continue
            
            # Para origens normais, verificar duplicatas
            if not cartorio_origem_id:
                logger.debug(f"DUPLICATA: Origem {i} normal sem cartório, pulando verificação")
                continue
                
            try:
                cartorio_origem = Cartorios.objects.get(id=cartorio_origem_id)
            except Cartorios.DoesNotExist:
                logger.debug(f"DUPLICATA: Cartório {cartorio_origem_id} não encontrado para origem {i}")
                continue
            
            # Verificar duplicata usando o service
            duplicata_info = DuplicataVerificacaoService.verificar_duplicata_origem(
                origem=origem,
                cartorio_id=cartorio_origem.id,
                imovel_atual_id=documento_ativo.imovel.id
            )

            if duplicata_info.get('existe', False):
                logger.debug(f"DUPLICATA: Duplicata encontrada na origem {i}: {origem}")
                # Reconstruct documento_origem using ID to avoid MultipleObjectsReturned
                documento_origem = Documento.objects.get(
                    id=duplicata_info['documento']['id']
                )
                return {
                    'tem_duplicata': True,
                    'duplicata_info': duplicata_info,
                    'mensagem': f"Encontrada duplicata: {duplicata_info['documento']['numero']}",
                    'documento_origem': documento_origem,
                    'documentos_importaveis': duplicata_info.get('documentos_importaveis', []),
                    'cadeia_dominial': duplicata_info.get('cadeia_dominial', {}).get('documentos', [])
                }
        
        # Se chegou até aqui, não há duplicatas
        return {
            'tem_duplicata': False,
            'mensagem': 'Nenhuma duplicata encontrada nas origens fornecidas'
        }
    
    @staticmethod
    def processar_importacao_duplicata(request, documento_ativo, usuario):
        """
        Processa a importação de uma cadeia dominial duplicada
        
        Args:
            request: HttpRequest com dados da importação
            documento_ativo: Documento ativo do imóvel
            usuario: Usuário que está fazendo a importação
            
        Returns:
            dict: Resultado da importação
        """
        documento_origem_id = request.POST.get('documento_origem_id')
        documentos_importaveis_ids = request.POST.getlist('documentos_importaveis[]')
        
        if not documento_origem_id:
            return {
                'sucesso': False,
                'mensagem': 'Documento de origem não especificado'
            }
        
        try:
            documento_origem = Documento.objects.get(id=documento_origem_id)
        except Documento.DoesNotExist:
            return {
                'sucesso': False,
                'mensagem': 'Documento de origem não encontrado'
            }
        
        # Converter IDs para lista de inteiros
        try:
            documentos_importaveis_ids = [int(id) for id in documentos_importaveis_ids if id.strip()]
        except ValueError:
            return {
                'sucesso': False,
                'mensagem': 'IDs de documentos inválidos'
            }
        
        # Verificar se os documentos existem
        documentos_importaveis = []
        for doc_id in documentos_importaveis_ids:
            try:
                doc = Documento.objects.get(id=doc_id)
                documentos_importaveis.append(doc)
            except Documento.DoesNotExist:
                return {
                    'sucesso': False,
                    'mensagem': f'Documento {doc_id} não encontrado'
                }
        
        # Realizar importação
        try:
            logger.debug(f"IMPORTACAO: Iniciando importação para imóvel {documento_ativo.imovel.id}")
            logger.debug(f"IMPORTACAO: Documento origem ID: {documento_origem.id}")
            logger.debug(f"IMPORTACAO: Documentos importáveis IDs: {documentos_importaveis_ids}")
            logger.debug(f"IMPORTACAO: Usuário ID: {usuario.id}")
            
            resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
                imovel_destino_id=documento_ativo.imovel.id,
                documento_origem_id=documento_origem.id,
                documentos_importaveis_ids=documentos_importaveis_ids,
                usuario_id=usuario.id
            )
            
            logger.debug(f"IMPORTACAO: Resultado recebido: {resultado}")
            
            if resultado['sucesso']:
                return {
                    'sucesso': True,
                    'mensagem': f"Importação realizada com sucesso! {resultado['documentos_importados']} documentos importados.",
                    'documentos_importados': resultado['documentos_importados']
                }
            else:
                erro_msg = resultado.get('erro', resultado.get('mensagem', 'Erro desconhecido na importação'))
                logger.debug(f"IMPORTACAO: Erro na importação: {erro_msg}")
                return {
                    'sucesso': False,
                    'mensagem': erro_msg
                }
                
        except Exception as e:
            logger.debug(f"IMPORTACAO: Exceção durante importação: {str(e)}")
            import traceback
            logger.debug(f"IMPORTACAO: Traceback: {traceback.format_exc()}")
            return {
                'sucesso': False,
                'mensagem': f'Erro durante importação: {str(e)}'
            }
    
    @staticmethod
    def obter_dados_duplicata_para_template(duplicata_info):
        """
        Prepara dados da duplicata para exibição no template

        Args:
            duplicata_info: Informações da duplicata encontrada

        Returns:
            dict: Dados formatados para o template
        """
        import logging
        logger = logging.getLogger(__name__)

        if not duplicata_info.get('tem_duplicata'):
            return None

        documento_origem = duplicata_info['documento_origem']
        documentos_importaveis = duplicata_info['documentos_importaveis']
        cadeia_dominial_raw = duplicata_info['cadeia_dominial']

        # DEFENSIVE: Handle both old (list) and new (dict with 'documentos' key) formats
        # Log which format we received for debugging
        if isinstance(cadeia_dominial_raw, dict):
            logger.warning(
                "DEFENSIVE: cadeia_dominial is dict (new format from DuplicataVerificacaoService). "
                f"Keys: {cadeia_dominial_raw.keys()}. Extracting 'documentos' list."
            )
            # New format: {'documento_origem': {...}, 'total_documentos': N, 'documentos': [...]}
            cadeia_dominial = cadeia_dominial_raw.get('documentos', [])
            if not cadeia_dominial:
                logger.error(
                    "DEFENSIVE: 'documentos' key missing or empty in cadeia_dominial dict. "
                    f"Available keys: {cadeia_dominial_raw.keys()}"
                )
        elif isinstance(cadeia_dominial_raw, list):
            logger.info("DEFENSIVE: cadeia_dominial is list (expected adapter output). Using directly.")
            # Old/expected format: Already a list of {'documento': ..., 'lancamentos': [...]}
            cadeia_dominial = cadeia_dominial_raw
        else:
            logger.error(
                f"DEFENSIVE: Unexpected cadeia_dominial type: {type(cadeia_dominial_raw)}. "
                "Defaulting to empty list to prevent template crash."
            )
            cadeia_dominial = []

        # Formatar dados para exibição
        dados_template = {
            'documento_origem': {
                'id': documento_origem.id,
                'numero': documento_origem.numero,
                'tipo': documento_origem.tipo.get_tipo_display(),
                'imovel_nome': documento_origem.imovel.nome,
                'cartorio': documento_origem.cartorio.nome if documento_origem.cartorio else 'Não informado',
                'livro': documento_origem.livro or 'Não informado',
                'folha': documento_origem.folha or 'Não informado',
                'total_lancamentos': documento_origem.lancamentos.count()
            },
            'documentos_importaveis': []
        }

        # Formatar documentos importáveis
        for doc in documentos_importaveis:
            dados_template['documentos_importaveis'].append({
                'id': doc.id,
                'numero': doc.numero,
                'tipo': doc.tipo.get_tipo_display(),
                'livro': doc.livro or 'Não informado',
                'folha': doc.folha or 'Não informado',
                'total_lancamentos': doc.lancamentos.count(),
                'selecionado': True  # Por padrão, todos selecionados
            })

        # Formatar cadeia dominial
        dados_template['cadeia_dominial'] = []
        try:
            for item in cadeia_dominial:
                # DEFENSIVE: Validate item structure
                if not isinstance(item, dict):
                    logger.error(
                        f"DEFENSIVE: cadeia_dominial item is not dict: {type(item)}. Skipping."
                    )
                    continue

                if 'documento' not in item:
                    logger.error(
                        f"DEFENSIVE: cadeia_dominial item missing 'documento' key. "
                        f"Available keys: {item.keys()}. Skipping."
                    )
                    continue

                dados_template['cadeia_dominial'].append({
                    'documento': {
                        'id': item['documento'].id,
                        'numero': item['documento'].numero,
                        'tipo': item['documento'].tipo.get_tipo_display(),
                        'livro': item['documento'].livro or 'Não informado',
                        'folha': item['documento'].folha or 'Não informado'
                    },
                    'lancamentos': [
                        {
                            'numero': lanc.numero_lancamento,
                            'tipo': lanc.tipo.get_tipo_display(),
                            'data': lanc.data.strftime('%d/%m/%Y') if lanc.data and hasattr(lanc.data, 'strftime') else (str(lanc.data) if lanc.data else 'Não informado'),
                            'observacoes': lanc.observacoes or 'Sem observações'
                        }
                        for lanc in item.get('lancamentos', [])
                    ]
                })
        except Exception as e:
            logger.error(
                f"DEFENSIVE: Exception formatting cadeia_dominial: {e}. "
                f"Type: {type(cadeia_dominial)}, Content: {cadeia_dominial}"
            )
            # Continue with empty cadeia_dominial to prevent complete failure

        logger.info(
            f"DEFENSIVE: Successfully formatted template data. "
            f"cadeia_dominial items: {len(dados_template['cadeia_dominial'])}"
        )

        return dados_template 