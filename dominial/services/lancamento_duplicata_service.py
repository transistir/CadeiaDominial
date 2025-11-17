"""
Service para integração da verificação de duplicatas com o processo de criação de lançamentos
"""

from .duplicata_verificacao_service import DuplicataVerificacaoService
from .importacao_cadeia_service import ImportacaoCadeiaService
from ..models import Documento, Cartorios


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
        
        print(f"DEBUG DUPLICATA: Origens recebidas: {origens}")
        print(f"DEBUG DUPLICATA: Cartórios origem recebidos: {cartorios_origem}")
        print(f"DEBUG DUPLICATA: Todos os campos POST: {list(request.POST.keys())}")
        
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
            
            print(f"DEBUG DUPLICATA: Verificando origem {i}: '{origem}'")
            print(f"DEBUG DUPLICATA: Cartório origem ID {i}: '{cartorio_origem_id}'")
            
            if not origem:
                continue
                
            # Verificar se é origem de fim de cadeia
            is_fim_cadeia = any(padrao in origem for padrao in padroes_fim_cadeia)
            
            if is_fim_cadeia:
                # Para origens de fim de cadeia, não verificar duplicatas
                print(f"DEBUG DUPLICATA: Origem {i} é fim de cadeia, pulando verificação")
                continue
            
            # Para origens normais, verificar duplicatas
            if not cartorio_origem_id:
                print(f"DEBUG DUPLICATA: Origem {i} normal sem cartório, pulando verificação")
                continue
                
            try:
                cartorio_origem = Cartorios.objects.get(id=cartorio_origem_id)
            except Cartorios.DoesNotExist:
                print(f"DEBUG DUPLICATA: Cartório {cartorio_origem_id} não encontrado para origem {i}")
                continue
            
            # Verificar duplicata usando o service
            duplicata_info = DuplicataVerificacaoService.verificar_duplicata_origem(
                origem=origem,
                cartorio_id=cartorio_origem.id,
                imovel_atual_id=documento_ativo.imovel.id
            )

            if duplicata_info.get('existe', False):
                print(f"DEBUG DUPLICATA: Duplicata encontrada na origem {i}: {origem}")
                # Reconstruct documento_origem from número and cartório
                documento_origem = Documento.objects.get(
                    numero=duplicata_info['documento']['numero'],
                    cartorio_id=cartorio_origem.id
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
            print(f"DEBUG IMPORTACAO: Iniciando importação para imóvel {documento_ativo.imovel.id}")
            print(f"DEBUG IMPORTACAO: Documento origem ID: {documento_origem.id}")
            print(f"DEBUG IMPORTACAO: Documentos importáveis IDs: {documentos_importaveis_ids}")
            print(f"DEBUG IMPORTACAO: Usuário ID: {usuario.id}")
            
            resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
                imovel_destino_id=documento_ativo.imovel.id,
                documento_origem_id=documento_origem.id,
                documentos_importaveis_ids=documentos_importaveis_ids,
                usuario_id=usuario.id
            )
            
            print(f"DEBUG IMPORTACAO: Resultado recebido: {resultado}")
            
            if resultado['sucesso']:
                return {
                    'sucesso': True,
                    'mensagem': f"Importação realizada com sucesso! {resultado['documentos_importados']} documentos importados.",
                    'documentos_importados': resultado['documentos_importados']
                }
            else:
                erro_msg = resultado.get('erro', resultado.get('mensagem', 'Erro desconhecido na importação'))
                print(f"DEBUG IMPORTACAO: Erro na importação: {erro_msg}")
                return {
                    'sucesso': False,
                    'mensagem': erro_msg
                }
                
        except Exception as e:
            print(f"DEBUG IMPORTACAO: Exceção durante importação: {str(e)}")
            import traceback
            print(f"DEBUG IMPORTACAO: Traceback: {traceback.format_exc()}")
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
        if not duplicata_info.get('tem_duplicata'):
            return None
        
        documento_origem = duplicata_info['documento_origem']
        documentos_importaveis = duplicata_info['documentos_importaveis']
        cadeia_dominial = duplicata_info['cadeia_dominial']
        
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
        for item in cadeia_dominial:
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
                    for lanc in item['lancamentos']
                ]
            })
        
        return dados_template 