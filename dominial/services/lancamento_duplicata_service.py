"""
Service para integração da verificação de duplicatas com o processo de criação de lançamentos
"""

from .duplicata_verificacao_service import DuplicataVerificacaoService
from .importacao_cadeia_service import ImportacaoCadeiaService
from ..models import Cartorios


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
            
            if duplicata_info['tem_duplicata']:
                print(f"DEBUG DUPLICATA: Duplicata encontrada na origem {i}: {origem}")
                return {
                    'tem_duplicata': True,
                    'duplicata_info': duplicata_info,
                    'mensagem': f"Encontrada duplicata: {duplicata_info['documento_origem'].numero} - {duplicata_info['documento_origem'].imovel.nome}",
                    'documento_origem': duplicata_info['documento_origem'],
                    'documentos_importaveis': duplicata_info['documentos_importaveis'],
                    'cadeia_dominial': duplicata_info['cadeia_dominial']
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
            documento_origem_id = int(documento_origem_id)
            documentos_importaveis_ids = [int(id) for id in documentos_importaveis_ids if id.strip()]
        except ValueError:
            return {
                'sucesso': False,
                'mensagem': 'IDs de documentos inválidos'
            }

        validacao = LancamentoDuplicataService._validar_identidade_duplicata(
            request, documento_origem_id, documentos_importaveis_ids, documento_ativo.imovel_id
        )
        if not validacao['sucesso']:
            return validacao

        documento_origem = validacao['documento_origem']
        documentos_importaveis = validacao['documentos_importaveis']

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
    def _validar_identidade_duplicata(request, documento_origem_id, documentos_importaveis_ids, imovel_atual_id):
        """
        Confirma o `documento_origem_id` e os `documentos_importaveis[]` recebidos
        no POST contra uma duplicata recalculada no servidor (T26).

        Nunca confia nos PKs enviados pelo formulário: a origem/cartório
        originalmente submetidos (preservados como campos ocultos) são
        reprocessados pelo mesmo fluxo de detecção de duplicata, e o
        documento de origem e a cadeia dominial resultantes precisam bater
        exatamente com o que o usuário está tentando importar.
        """
        origens = request.POST.getlist('origem_completa[]')
        cartorios_origem = request.POST.getlist('cartorio_origem[]')

        for i, origem in enumerate(origens):
            origem = origem.strip() if origem else ''
            cartorio_origem_id = cartorios_origem[i] if i < len(cartorios_origem) and cartorios_origem[i] else None
            if not origem or not cartorio_origem_id:
                continue

            try:
                cartorio_origem = Cartorios.objects.get(id=cartorio_origem_id)
            except (Cartorios.DoesNotExist, ValueError):
                continue

            duplicata_info = DuplicataVerificacaoService.verificar_duplicata_origem(
                origem=origem,
                cartorio_id=cartorio_origem.id,
                imovel_atual_id=imovel_atual_id
            )
            if not duplicata_info.get('tem_duplicata'):
                continue

            documento_origem = duplicata_info['documento_origem']
            if documento_origem.id != documento_origem_id:
                continue

            cadeia_por_id = {
                item['documento'].id: item['documento']
                for item in duplicata_info['cadeia_dominial']
            }
            if not set(documentos_importaveis_ids).issubset(cadeia_por_id.keys()):
                return {
                    'sucesso': False,
                    'mensagem': 'Os documentos selecionados não pertencem à cadeia dominial identificada.'
                }

            return {
                'sucesso': True,
                'documento_origem': documento_origem,
                'documentos_importaveis': [
                    cadeia_por_id[doc_id] for doc_id in documentos_importaveis_ids
                ]
            }

        return {
            'sucesso': False,
            'mensagem': 'Não foi possível confirmar a duplicata: origem e cartório informados não correspondem ao documento selecionado.'
        }

    @staticmethod
    def _identidade_documento(documento):
        """Bloco de identidade documental completa para apresentação (T25).

        Reúne tipo, número, cartório (com CNS e localização) e imóvel, de forma
        suficiente para distinguir homônimos em cartórios diferentes. Apenas
        adiciona dados de apresentação; não altera o contrato de seleção (IDs e
        campos existentes seguem iguais até a T26).
        """
        cartorio = documento.cartorio
        imovel = documento.imovel
        return {
            'cartorio': cartorio.nome if cartorio else 'Não informado',
            'cartorio_cns': cartorio.cns if cartorio and cartorio.cns else '',
            'cartorio_cidade': cartorio.cidade if cartorio and cartorio.cidade else '',
            'cartorio_uf': cartorio.estado if cartorio and cartorio.estado else '',
            'imovel_id': imovel.id if imovel else None,
            'imovel_nome': imovel.nome if imovel else 'Não informado',
            'imovel_matricula': imovel.matricula if imovel else '',
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
        documento_origem_dados = {
            'id': documento_origem.id,
            'numero': documento_origem.numero,
            'tipo': documento_origem.tipo.get_tipo_display(),
            'livro': documento_origem.livro or 'Não informado',
            'folha': documento_origem.folha or 'Não informado',
            'total_lancamentos': documento_origem.lancamentos.count(),
        }
        documento_origem_dados.update(
            LancamentoDuplicataService._identidade_documento(documento_origem)
        )
        dados_template = {
            'documento_origem': documento_origem_dados,
            'documentos_importaveis': []
        }

        # Formatar documentos importáveis
        for doc in documentos_importaveis:
            item = {
                'id': doc.id,
                'numero': doc.numero,
                'tipo': doc.tipo.get_tipo_display(),
                'livro': doc.livro or 'Não informado',
                'folha': doc.folha or 'Não informado',
                'total_lancamentos': doc.lancamentos.count(),
                'selecionado': True  # Por padrão, todos selecionados
            }
            item.update(LancamentoDuplicataService._identidade_documento(doc))
            dados_template['documentos_importaveis'].append(item)

        # Formatar cadeia dominial
        dados_template['cadeia_dominial'] = []
        for item in cadeia_dominial:
            documento_dados = {
                'id': item['documento'].id,
                'numero': item['documento'].numero,
                'tipo': item['documento'].tipo.get_tipo_display(),
                'livro': item['documento'].livro or 'Não informado',
                'folha': item['documento'].folha or 'Não informado',
            }
            documento_dados.update(
                LancamentoDuplicataService._identidade_documento(item['documento'])
            )
            dados_template['cadeia_dominial'].append({
                'documento': documento_dados,
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