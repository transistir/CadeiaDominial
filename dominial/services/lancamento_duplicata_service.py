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
        
        # Pegar a primeira origem e cartório (se houver)
        origem = origens[0].strip() if origens and origens[0].strip() else ''
        cartorio_origem_id = cartorios_origem[0] if cartorios_origem and cartorios_origem[0] else None
        
        print(f"DEBUG DUPLICATA: Origem processada: '{origem}'")
        print(f"DEBUG DUPLICATA: Cartório origem ID processado: '{cartorio_origem_id}'")
        
        if not origem or not cartorio_origem_id:
            return {
                'tem_duplicata': False,
                'mensagem': 'Origem ou cartório de origem não fornecidos para verificação'
            }
        
        try:
            cartorio_origem = Cartorios.objects.get(id=cartorio_origem_id)
        except Cartorios.DoesNotExist:
            return {
                'tem_duplicata': False,
                'mensagem': 'Cartório de origem não encontrado'
            }
        
        # Verificar duplicata usando o service
        duplicata_info = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem=origem,
            cartorio_id=cartorio_origem.id,
            imovel_atual_id=documento_ativo.imovel.id
        )
        
        if duplicata_info['tem_duplicata']:
            return {
                'tem_duplicata': True,
                'duplicata_info': duplicata_info,
                'mensagem': f"Encontrada duplicata: {duplicata_info['documento_origem'].numero} - {duplicata_info['documento_origem'].imovel.nome}",
                'documento_origem': duplicata_info['documento_origem'],
                'documentos_importaveis': duplicata_info['documentos_importaveis'],
                'cadeia_dominial': duplicata_info['cadeia_dominial']
            }
        else:
            return {
                'tem_duplicata': False,
                'mensagem': 'Nenhuma duplicata encontrada'
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
            resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
                imovel_destino_id=documento_ativo.imovel.id,
                documento_origem_id=documento_origem.id,
                documentos_importaveis_ids=documentos_importaveis_ids,
                usuario_id=usuario.id
            )
            
            if resultado['sucesso']:
                return {
                    'sucesso': True,
                    'mensagem': f"Importação realizada com sucesso! {resultado['documentos_importados']} documentos importados.",
                    'documentos_importados': resultado['documentos_importados']
                }
            else:
                return {
                    'sucesso': False,
                    'mensagem': resultado['mensagem']
                }
                
        except Exception as e:
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
                        'data': lanc.data.strftime('%d/%m/%Y') if lanc.data else 'Não informado',
                        'observacoes': lanc.observacoes or 'Sem observações'
                    }
                    for lanc in item['lancamentos']
                ]
            })
        
        return dados_template 