"""
Patch para resolver o problema de conexão T1004 -> T2822
Aplica melhorias no HierarquiaArvoreService original
"""

def aplicar_patch_hierarquia_arvore_service():
    """
    Aplica patch no HierarquiaArvoreService para resolver problemas de conexão
    """
    
    # Importar o serviço original
    from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
    import re
    import logging
    
    logger = logging.getLogger(__name__)
    
    def extrair_origens_robusto(origem_texto):
        """
        Versão melhorada da extração de origens
        """
        if not origem_texto:
            return []
        
        origens = []
        
        # Padrão 1: M/T seguido de números (padrão atual)
        padrao1 = re.findall(r'[MT]\d+', origem_texto)
        origens.extend(padrao1)
        
        # Padrão 2: M/T com separadores (espaços, hífens, pontos)
        padrao2 = re.findall(r'[MT]\s*[-.]?\s*\d+', origem_texto)
        for match in padrao2:
            # Limpar e normalizar
            limpo = re.sub(r'\s*[-.]?\s*', '', match)
            if limpo not in origens:
                origens.append(limpo)
        
        # Padrão 3: Números simples (assumir como matrícula se >= 3 dígitos)
        padrao3 = re.findall(r'\b\d{3,}\b', origem_texto)
        for num in padrao3:
            # Verificar se não está já capturado em outros padrões
            if not any(f'M{num}' in origem_texto or f'T{num}' in origem_texto for _ in [1]):
                # Assumir como matrícula por padrão
                if f'M{num}' not in origens:
                    origens.append(f'M{num}')
        
        # Padrão 4: Busca por texto livre
        # Procurar por "transcrição" + número
        padrao4 = re.findall(r'transcri[çc][ãa]o\s*(\d+)', origem_texto, re.IGNORECASE)
        for num in padrao4:
            if f'T{num}' not in origens:
                origens.append(f'T{num}')
        
        # Procurar por "matrícula" + número
        padrao5 = re.findall(r'matr[íi]cula\s*(\d+)', origem_texto, re.IGNORECASE)
        for num in padrao5:
            if f'M{num}' not in origens:
                origens.append(f'M{num}')
        
        # Remover duplicatas e retornar
        return list(set(origens))
    
    def buscar_documento_origem_robusto(origem_numero, cartorio_origem=None, lancamento=None):
        """
        Busca documento de origem APENAS no cartório de origem especificado
        CORREÇÃO: Não busca em outros cartórios para evitar conexões incorretas
        """
        from dominial.models import Documento
        
        logger.info(f"🔍 Buscando documento origem: {origem_numero}")
        
        # REGRA: Buscar APENAS no cartório de origem especificado
        if cartorio_origem:
            # Estratégia 1: Buscar exatamente como especificado
            doc = Documento.objects.filter(
                numero=origem_numero,
                cartorio=cartorio_origem
            ).first()
            
            if doc:
                logger.info(f"✅ Documento {origem_numero} encontrado no cartório de origem {cartorio_origem.nome}")
                return doc
            
            # Estratégia 2: Buscar por variações do número no MESMO cartório
            numero_limpo = re.sub(r'^[MT]', '', origem_numero)
            if numero_limpo.isdigit():
                # Buscar com prefixo M no mesmo cartório
                doc_m = Documento.objects.filter(
                    numero=f'M{numero_limpo}',
                    cartorio=cartorio_origem
                ).first()
                if doc_m:
                    logger.info(f"✅ Documento encontrado como M{numero_limpo} no cartório {cartorio_origem.nome}")
                    return doc_m
                
                # Buscar com prefixo T no mesmo cartório
                doc_t = Documento.objects.filter(
                    numero=f'T{numero_limpo}',
                    cartorio=cartorio_origem
                ).first()
                if doc_t:
                    logger.info(f"✅ Documento encontrado como T{numero_limpo} no cartório {cartorio_origem.nome}")
                    return doc_t
            
            logger.warning(f"❌ Documento {origem_numero} não encontrado no cartório de origem {cartorio_origem.nome}")
            return None
        
        # Se não tem cartório de origem especificado, não buscar em lugar nenhum
        logger.warning(f"❌ Cartório de origem não especificado para {origem_numero} - não buscando")
        return None
    
    # Substituir o método _buscar_documentos_pais
    def _buscar_documentos_pais_melhorado(documento, imovel, criar_documentos_automaticos):
        """
        Versão melhorada para buscar documentos pais (origens)
        """
        from dominial.models import Documento
        from collections import deque
        
        documentos_pais = []
        documentos_processados = set()
        
        logger.info(f"🔍 Buscando documentos pais para {documento.numero}")
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        logger.info(f"📋 Encontrados {lancamentos.count()} lançamentos com origens")
        
        for lancamento in lancamentos:
            logger.info(f"📝 Processando lançamento {lancamento.id}: {lancamento.origem}")
            
            # Extrair origens com método robusto
            origens = extrair_origens_robusto(lancamento.origem)
            
            logger.info(f"🎯 Origens extraídas: {origens}")
            
            for origem_numero in origens:
                if origem_numero in documentos_processados:
                    logger.info(f"⏭️ Origem {origem_numero} já processada, pulando")
                    continue
                
                documentos_processados.add(origem_numero)
                
                # Buscar documento com método robusto
                doc_pai = buscar_documento_origem_robusto(
                    origem_numero, 
                    lancamento.cartorio_origem, 
                    lancamento
                )
                
                if doc_pai:
                    logger.info(f"✅ Documento pai encontrado: {doc_pai.numero} (ID: {doc_pai.id})")
                    documentos_pais.append(doc_pai)
                else:
                    logger.warning(f"❌ Documento {origem_numero} não encontrado")
        
        logger.info(f"📊 Total de documentos pais encontrados: {len(documentos_pais)}")
        return documentos_pais
    
    # Aplicar o patch
    HierarquiaArvoreService._buscar_documentos_pais = _buscar_documentos_pais_melhorado
    
    logger.info("✅ Patch aplicado com sucesso no HierarquiaArvoreService")
    
    return True


if __name__ == "__main__":
    aplicar_patch_hierarquia_arvore_service()
