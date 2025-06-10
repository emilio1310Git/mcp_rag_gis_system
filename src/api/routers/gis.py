"""Router para endpoints de análisis GIS"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...services.gis_service import GISService
from ...services.maps_service import MapsService
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
gis_service = GISService()
maps_service = MapsService()

class CensusSectionInfo(BaseModel):
    """Información de sección censal"""
    codigo_seccion: str
    codigo_distrito: str
    codigo_municipio: str
    nombre_municipio: str
    poblacion: int
    superficie_km2: float
    densidad_hab_km2: float
    centroid_lat: float
    centroid_lon: float

class CensusSectionsResponse(BaseModel):
    """Respuesta de secciones censales"""
    total_sections: int
    total_population: int
    average_density: float
    total_area: float
    sections: List[CensusSectionInfo]

class SpatialAnalysisRequest(BaseModel):
    """Solicitud de análisis espacial"""
    address: str
    radius: int = 2000
    buffer_meters: int = 500
    facility_types: Optional[List[str]] = None

class SpatialAnalysisResponse(BaseModel):
    """Respuesta de análisis espacial"""
    address: str
    latitude: float
    longitude: float
    radius: int
    buffer_meters: int
    total_facilities: int
    total_intersections: int
    affected_sections: List[Dict[str, Any]]

class CoverageAnalysisResponse(BaseModel):
    """Respuesta de análisis de cobertura"""
    facility_type: str
    max_distance_meters: int
    total_sections: int
    covered_sections: int
    sections_coverage_percentage: float
    total_population: int
    covered_population: int
    population_coverage_percentage: float
    coverage_rating: str
    recommendations: List[str]

class OptimalLocationInfo(BaseModel):
    """Información de ubicación óptima"""
    codigo_seccion: str
    latitude: float
    longitude: float
    population_served: int
    density: float
    location_score: float
    justification: str

class OptimalLocationsResponse(BaseModel):
    """Respuesta de ubicaciones óptimas"""
    facility_type: str
    num_requested: int
    optimal_locations: List[OptimalLocationInfo]

@router.get("/census-sections", response_model=CensusSectionsResponse)
async def get_census_sections(
    municipio: Optional[str] = Query(None, description="Filtrar por municipio"),
    bbox: Optional[str] = Query(None, description="Bounding box como 'xmin,ymin,xmax,ymax'")
):
    """Obtener secciones censales con filtros opcionales"""
    try:
        # Parsear bbox si se proporciona
        bbox_tuple = None
        if bbox:
            try:
                bbox_parts = [float(x.strip()) for x in bbox.split(',')]
                if len(bbox_parts) == 4:
                    bbox_tuple = tuple(bbox_parts)
                else:
                    raise ValueError("Bbox debe tener 4 valores")
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de bbox inválido. Use: 'xmin,ymin,xmax,ymax'")
        
        # Obtener secciones
        sections_gdf = await gis_service.get_census_sections(bbox_tuple, municipio)
        
        if sections_gdf.empty:
            return CensusSectionsResponse(
                total_sections=0,
                total_population=0,
                average_density=0,
                total_area=0,
                sections=[]
            )
        
        # Convertir a lista de objetos
        sections_list = []
        for idx, section in sections_gdf.iterrows():
            sections_list.append(CensusSectionInfo(
                codigo_seccion=section['codigo_seccion'],
                codigo_distrito=section['codigo_distrito'],
                codigo_municipio=section['codigo_municipio'],
                nombre_municipio=section['nombre_municipio'],
                poblacion=section['poblacion'],
                superficie_km2=section['superficie_km2'],
                densidad_hab_km2=section['densidad_hab_km2'],
                centroid_lat=section['centroid_lat'],
                centroid_lon=section['centroid_lon']
            ))
        
        return CensusSectionsResponse(
            total_sections=len(sections_gdf),
            total_population=int(sections_gdf['poblacion'].sum()),
            average_density=float(sections_gdf['densidad_hab_km2'].mean()),
            total_area=float(sections_gdf['superficie_km2'].sum()),
            sections=sections_list[:50]  # Limitar respuesta
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo secciones censales: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/spatial-analysis", response_model=SpatialAnalysisResponse)
async def spatial_analysis(request: SpatialAnalysisRequest):
    """Realizar análisis espacial entre equipamientos y secciones censales"""
    try:
        # Geocodificar dirección
        lat, lon = await maps_service.geocode_address(request.address)
        
        # Buscar equipamientos
        facilities = await maps_service.find_facilities_nearby(lat, lon, request.radius)
        
        # Filtrar tipos específicos si se especificaron
        if request.facility_types:
            facilities = {k: v for k, v in facilities.items() if k in request.facility_types}
        
        # Convertir a lista plana
        all_facilities = []
        for facility_type, facility_list in facilities.items():
            all_facilities.extend(facility_list)
        
        if not all_facilities:
            raise HTTPException(status_code=404, detail="No se encontraron equipamientos")
        
        # Realizar análisis espacial
        spatial_results = await gis_service.spatial_join_facilities_sections(
            all_facilities, request.buffer_meters
        )
        
        # Agrupar resultados por sección censal
        sections_summary = {}
        for result in spatial_results:
            section_code = result['codigo_seccion']
            if section_code not in sections_summary:
                sections_summary[section_code] = {
                    'codigo_seccion': section_code,
                    'nombre_municipio': result['nombre_municipio'],
                    'poblacion': result['poblacion'],
                    'densidad_hab_km2': result['densidad_hab_km2'],
                    'equipamientos': [],
                    'accesibilidad_promedio': 0
                }
            
            sections_summary[section_code]['equipamientos'].append({
                'nombre': result['facility_name'],
                'tipo': result['facility_type'],
                'distancia_metros': result['distance_to_section_meters'],
                'score_accesibilidad': result['accesibilidad_score']
            })
        
        # Calcular score promedio de accesibilidad por sección
        for section_data in sections_summary.values():
            if section_data['equipamientos']:
                avg_score = sum(eq['score_accesibilidad'] for eq in section_data['equipamientos']) / len(section_data['equipamientos'])
                section_data['accesibilidad_promedio'] = round(avg_score, 2)
        
        return SpatialAnalysisResponse(
            address=request.address,
            latitude=lat,
            longitude=lon,
            radius=request.radius,
            buffer_meters=request.buffer_meters,
            total_facilities=len(all_facilities),
            total_intersections=len(spatial_results),
            affected_sections=list(sections_summary.values())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en análisis espacial: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")

@router.get("/coverage-analysis/{facility_type}", response_model=CoverageAnalysisResponse)
async def analyze_coverage(
    facility_type: str,
    max_distance: int = Query(1000, description="Distancia máxima de cobertura en metros"),
    municipio: Optional[str] = Query(None, description="Municipio específico")
):
    """Analizar cobertura de un tipo de equipamiento"""
    try:
        # Validar tipo de equipamiento
        if facility_type not in settings.gis.facility_types:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de equipamiento inválido. Tipos válidos: {list(settings.gis.facility_types.keys())}"
            )
        
        # Realizar análisis de cobertura
        coverage_stats = await gis_service.analyze_facility_coverage(
            facility_type, max_distance, municipio
        )
        
        if not coverage_stats:
            raise HTTPException(status_code=404, detail="No se encontraron datos para el análisis")
        
        return CoverageAnalysisResponse(
            facility_type=facility_type,
            max_distance_meters=max_distance,
            total_sections=coverage_stats.get('total_secciones', 0),
            covered_sections=coverage_stats.get('secciones_con_cobertura', 0),
            sections_coverage_percentage=coverage_stats.get('porcentaje_secciones_cubiertas', 0),
            total_population=coverage_stats.get('poblacion_total', 0),
            covered_population=coverage_stats.get('poblacion_cubierta', 0),
            population_coverage_percentage=coverage_stats.get('porcentaje_poblacion_cubierta', 0),
            coverage_rating=coverage_stats.get('calificacion_cobertura', 'desconocida'),
            recommendations=coverage_stats.get('recomendaciones', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analizando cobertura: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")

@router.get("/optimal-locations/{facility_type}", response_model=OptimalLocationsResponse)
async def find_optimal_locations(
    facility_type: str,
    num_locations: int = Query(3, description="Número de ubicaciones a sugerir", ge=1, le=10)
):
    """Encontrar ubicaciones óptimas para nuevos equipamientos"""
    try:
        # Validar tipo de equipamiento
        if facility_type not in settings.gis.facility_types:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de equipamiento inválido. Tipos válidos: {list(settings.gis.facility_types.keys())}"
            )
        
        # Buscar ubicaciones óptimas
        optimal_locations = await gis_service.find_optimal_locations(
            facility_type, num_locations
        )
        
        # Convertir a objetos de respuesta
        locations_list = []
        for location in optimal_locations:
            locations_list.append(OptimalLocationInfo(
                codigo_seccion=location['codigo_seccion'],
                latitude=location['lat'],
                longitude=location['lon'],
                population_served=location['poblacion_servida'],
                density=location['densidad'],
                location_score=location['score_ubicacion'],
                justification=location['justificacion']
            ))
        
        return OptimalLocationsResponse(
            facility_type=facility_type,
            num_requested=num_locations,
            optimal_locations=locations_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error encontrando ubicaciones óptimas: {e}")
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

@router.post("/coverage-map/{facility_type}")
async def create_coverage_map(
    facility_type: str,
    center_address: str,
    show_sections: bool = Query(True, description="Mostrar secciones censales"),
    zoom_level: int = Query(12, description="Nivel de zoom del mapa")
):
    """Crear mapa de cobertura con secciones censales"""
    try:
        # Validar tipo de equipamiento
        if facility_type not in settings.gis.facility_types:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de equipamiento inválido. Tipos válidos: {list(settings.gis.facility_types.keys())}"
            )
        
        # Geocodificar dirección central
        center_lat, center_lon = await maps_service.geocode_address(center_address)
        
        # Crear mapa de cobertura
        map_filename = await gis_service.create_coverage_map(
            facility_type, center_lat, center_lon, 
            zoom_level=zoom_level, show_sections=show_sections
        )
        
        map_url = f"http://{settings.api.host}:{settings.api.port}/map/{map_filename}"
        
        return {
            "map_filename": map_filename,
            "map_url": map_url,
            "facility_type": facility_type,
            "center_address": center_address,
            "center_latitude": center_lat,
            "center_longitude": center_lon,
            "shows_sections": show_sections
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando mapa de cobertura: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando mapa: {str(e)}")

@router.post("/accessibility-report")
async def generate_accessibility_report(
    municipio: str,
    facility_types: Optional[List[str]] = None
):
    """Generar informe completo de accesibilidad"""
    try:
        # Validar tipos de equipamientos si se especifican
        if facility_types:
            valid_types = set(settings.gis.facility_types.keys())
            invalid_types = set(facility_types) - valid_types
            if invalid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipos de equipamiento inválidos: {invalid_types}"
                )
        
        # Generar informe
        report = await gis_service.generate_accessibility_report(municipio, facility_types)
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando informe: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando informe: {str(e)}")
