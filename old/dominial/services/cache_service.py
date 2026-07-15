"""
Service para gerenciamento de cache de queries frequentes
"""
from django.core.cache import cache
from django.conf import settings
from ..models import Documento, Lancamento, TIs, Imovel, Cartorios, Pessoas
from typing import List, Dict, Any, Optional
import hashlib
import json


class CacheService:
    """
    Service para gerenciar cache de queries frequentes e otimizar performance
    """
    
    # Tempo padrão de cache (em segundos)
    DEFAULT_CACHE_TIME = 300  # 5 minutos
    
    @staticmethod
    def _generate_cache_key(prefix: str, params: Dict[str, Any]) -> str:
        """
        Gera uma chave única para o cache baseada nos parâmetros
        """
        # Ordenar parâmetros para garantir consistência
        sorted_params = sorted(params.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        
        # Criar hash da string de parâmetros
        hash_obj = hashlib.md5(params_str.encode())
        hash_hex = hash_obj.hexdigest()
        
        return f"cadeia_dominial:{prefix}:{hash_hex}"
    
    @staticmethod
    def get_cached_documentos_imovel(imovel_id: int, use_cache: bool = True) -> Optional[List[Documento]]:
        """
        Obtém documentos de um imóvel com cache opcional
        """
        if not use_cache:
            return None
            
        cache_key = CacheService._generate_cache_key("documentos_imovel", {"imovel_id": imovel_id})
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        return None
    
    @staticmethod
    def set_cached_documentos_imovel(imovel_id: int, documentos: List[Documento], cache_time: int = None) -> None:
        """
        Armazena documentos de um imóvel no cache
        """
        if cache_time is None:
            cache_time = CacheService.DEFAULT_CACHE_TIME
            
        cache_key = CacheService._generate_cache_key("documentos_imovel", {"imovel_id": imovel_id})
        cache.set(cache_key, documentos, cache_time)
    
    @staticmethod
    def invalidate_documentos_imovel(imovel_id: int) -> None:
        """
        Invalida o cache de documentos de um imóvel
        """
        cache_key = CacheService._generate_cache_key("documentos_imovel", {"imovel_id": imovel_id})
        cache.delete(cache_key)
    
    @staticmethod
    def get_cached_lancamentos_documento(documento_id: int, use_cache: bool = True) -> Optional[List[Lancamento]]:
        """
        Obtém lançamentos de um documento com cache opcional
        """
        if not use_cache:
            return None
            
        cache_key = CacheService._generate_cache_key("lancamentos_documento", {"documento_id": documento_id})
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        return None
    
    @staticmethod
    def set_cached_lancamentos_documento(documento_id: int, lancamentos: List[Lancamento], cache_time: int = None) -> None:
        """
        Armazena lançamentos de um documento no cache
        """
        if cache_time is None:
            cache_time = CacheService.DEFAULT_CACHE_TIME
            
        cache_key = CacheService._generate_cache_key("lancamentos_documento", {"documento_id": documento_id})
        cache.set(cache_key, lancamentos, cache_time)
    
    @staticmethod
    def invalidate_lancamentos_documento(documento_id: int) -> None:
        """
        Invalida o cache de lançamentos de um documento
        """
        cache_key = CacheService._generate_cache_key("lancamentos_documento", {"documento_id": documento_id})
        cache.delete(cache_key)
    
    @staticmethod
    def get_cached_tronco_principal(imovel_id: int, use_cache: bool = True) -> Optional[List[Documento]]:
        """
        Obtém tronco principal de um imóvel com cache opcional
        """
        if not use_cache:
            return None
            
        cache_key = CacheService._generate_cache_key("tronco_principal", {"imovel_id": imovel_id})
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        return None
    
    @staticmethod
    def set_cached_tronco_principal(imovel_id: int, tronco: List[Documento], cache_time: int = None) -> None:
        """
        Armazena tronco principal de um imóvel no cache
        """
        if cache_time is None:
            cache_time = CacheService.DEFAULT_CACHE_TIME
            
        cache_key = CacheService._generate_cache_key("tronco_principal", {"imovel_id": imovel_id})
        cache.set(cache_key, tronco, cache_time)
    
    @staticmethod
    def invalidate_tronco_principal(imovel_id: int) -> None:
        """
        Invalida o cache do tronco principal de um imóvel
        """
        cache_key = CacheService._generate_cache_key("tronco_principal", {"imovel_id": imovel_id})
        cache.delete(cache_key)
    
    @staticmethod
    def clear_all_caches() -> None:
        """
        Limpa todos os caches do sistema
        """
        # Buscar e deletar todas as chaves que começam com o prefixo do sistema
        cache.clear()
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Retorna estatísticas do cache (se disponível)
        """
        # Esta é uma implementação básica - pode ser expandida conforme necessário
        return {
            "cache_enabled": hasattr(settings, 'CACHES'),
            "default_timeout": CacheService.DEFAULT_CACHE_TIME,
            "cache_backend": getattr(settings, 'CACHE_BACKEND', 'default')
        } 