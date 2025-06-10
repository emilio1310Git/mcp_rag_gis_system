"""Utilidades de geocodificación"""

import logging
from typing import Tuple, Optional, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

logger = logging.getLogger(__name__)

class GeocodingService:
    """Servicio de geocodificación con cache y retry"""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="mcp_gis_system_v2")
        self.cache = {}  # Cache simple en memoria
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def geocode(self, address: str) -> Tuple[float, float]:
        """Geocodificar dirección con cache y retry"""
        # Normalizar dirección para cache
        normalized_address = address.lower().strip()
        
        # Verificar cache
        if normalized_address in self.cache:
            logger.info(f"Cache hit para: {address}")
            return self.cache[normalized_address]
        
        # Intentar geocodificación con retry
        for attempt in range(self.max_retries):
            try:
                location = self.geolocator.geocode(
                    address, 
                    timeout=10,
                    exactly_one=True
                )
                
                if location:
                    coords = (location.latitude, location.longitude)
                    
                    # Guardar en cache
                    self.cache[normalized_address] = coords
                    
                    logger.info(f"Geocodificación exitosa: {address} -> {coords}")
                    return coords
                else:
                    raise ValueError(f"No se encontraron coordenadas para: {address}")
                    
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                logger.warning(f"Intento {attempt + 1} fallido para {address}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
            except Exception as e:
                logger.error(f"Error geocodificando {address}: {e}")
                raise
        
        raise RuntimeError(f"No se pudo geocodificar después de {self.max_retries} intentos")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        return {
            "cached_addresses": len(self.cache),
            "cache_keys": list(self.cache.keys())
        }
    
    def clear_cache(self):
        """Limpiar cache"""
        self.cache.clear()
        logger.info("Cache de geocodificación limpiado")