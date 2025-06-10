"""Router para endpoints de mapas"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...services.maps_service import MapsService
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
maps_service = MapsService()

class GeocodeResponse(BaseModel):
    """Respuesta de geocodificación"""
    address: str
    latitude: float
    longitude: float

class FacilityInfo(BaseModel):
    """Información de equipamiento"""
    name: str
    type: str
    latitude: float
    longitude: float
    distance: int
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[str] = None

class FacilitiesResponse(BaseModel):
    """Respuesta de búsqueda de equipamientos"""
    address: str
    latitude: float
    longitude: float
    radius: int
    total_facilities: int
    facilities_by_type: dict

class MapResponse(BaseModel):
    """Respuesta de creación de mapa"""
    map_filename: str
    map_url: str
    center_address: str
    latitude: float
    longitude: float
    total_facilities: int

@router.get("/geocode", response_model=GeocodeResponse)
async def geocode_address(address: str = Query(..., description="Dirección a geocodificar")):
    """Geocodificar una dirección"""
    try:
        lat, lon = await maps_service.geocode_address(address)
        
        return GeocodeResponse(
            address=address,
            latitude=lat,
            longitude=lon
        )
        
    except Exception as e:
        logger.error(f"Error geocodificando {address}: {e}")
        raise HTTPException(status_code=400, detail=f"Error geocodificando: {str(e)}")

@router.get("/facilities", response_model=FacilitiesResponse)
async def find_facilities(
    address: str = Query(..., description="Dirección de referencia"),
    radius: int = Query(2000, description="Radio de búsqueda en metros", ge=100, le=10000),
    facility_types: Optional[List[str]] = Query(None, description="Tipos específicos de equipamientos")
):
    """Buscar equipamientos públicos cercanos"""
    try:
        # Geocodificar dirección
        lat, lon = await maps_service.geocode_address(address)
        
        # Buscar equipamientos
        facilities = await maps_service.find_facilities_nearby(lat, lon, radius)
        
        # Filtrar tipos específicos si se especificaron
        if facility_types:
            valid_types = set(settings.gis.facility_types.keys())
            invalid_types = set(facility_types) - valid_types
            if invalid_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipos de equipamiento inválidos: {invalid_types}"
                )
            
            facilities = {k: v for k, v in facilities.items() if k in facility_types}
        
        # Calcular total de equipamientos
        total_facilities = sum(len(facility_list) for facility_list in facilities.values())
        
        return FacilitiesResponse(
            address=address,
            latitude=lat,
            longitude=lon,
            radius=radius,
            total_facilities=total_facilities,
            facilities_by_type=facilities
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error buscando equipamientos: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/create-map", response_model=MapResponse)
async def create_map(
    address: str,
    radius: int = 1500,
    include_census: bool = False
):
    """Crear mapa interactivo con equipamientos"""
    try:
        # Geocodificar dirección
        lat, lon = await maps_service.geocode_address(address)
        
        # Buscar equipamientos
        facilities = await maps_service.find_facilities_nearby(lat, lon, radius)
        
        # Crear mapa
        map_filename = await maps_service.create_interactive_map(
            address, lat, lon, facilities, include_census
        )
        
        # Calcular total de equipamientos
        total_facilities = sum(len(facility_list) for facility_list in facilities.values())
        
        map_url = f"http://{settings.api.host}:{settings.api.port}/map/{map_filename}"
        
        return MapResponse(
            map_filename=map_filename,
            map_url=map_url,
            center_address=address,
            latitude=lat,
            longitude=lon,
            total_facilities=total_facilities
        )
        
    except Exception as e:
        logger.error(f"Error creando mapa: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando mapa: {str(e)}")

@router.get("/facility-types")
async def get_facility_types():
    """Obtener tipos de equipamientos soportados"""
    return {
        "facility_types": {
            key: {
                "name": config["name"],
                "icon": config["icon"],
                "color": config["color"],
                "priority": config.get("priority", 10)
            }
            for key, config in settings.gis.facility_types.items()
        }
    }
