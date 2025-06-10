"""Utilidades para análisis espacial"""

import logging
from typing import List, Dict, Any, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import pyproj
from functools import partial

logger = logging.getLogger(__name__)

class SpatialAnalyzer:
    """Analizador espacial con utilidades geométricas"""
    
    def __init__(self, source_crs: str = "EPSG:4326", target_crs: str = "EPSG:3857"):
        self.source_crs = source_crs
        self.target_crs = target_crs
        
        # Configurar transformadores
        self.to_projected = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True
        ).transform
        
        self.to_geographic = pyproj.Transformer.from_crs(
            target_crs, source_crs, always_xy=True
        ).transform
    
    def create_buffer(
        self, 
        lat: float, 
        lon: float, 
        radius_meters: float
    ) -> Polygon:
        """Crear buffer en metros alrededor de un punto"""
        # Crear punto
        point = Point(lon, lat)
        
        # Transformar a coordenadas proyectadas
        projected_point = transform(self.to_projected, point)
        
        # Crear buffer en metros
        buffered = projected_point.buffer(radius_meters)
        
        # Transformar de vuelta a geográficas
        geographic_buffer = transform(self.to_geographic, buffered)
        
        return geographic_buffer
    
    def calculate_distance_matrix(
        self, 
        origins: List[Tuple[float, float]], 
        destinations: List[Tuple[float, float]]
    ) -> pd.DataFrame:
        """Calcular matriz de distancias entre puntos"""
        # Crear GeoDataFrames
        origins_gdf = gpd.GeoDataFrame(
            geometry=[Point(lon, lat) for lat, lon in origins],
            crs=self.source_crs
        )
        
        destinations_gdf = gpd.GeoDataFrame(
            geometry=[Point(lon, lat) for lat, lon in destinations],
            crs=self.source_crs
        )
        
        # Proyectar para cálculos precisos de distancia
        origins_proj = origins_gdf.to_crs(self.target_crs)
        destinations_proj = destinations_gdf.to_crs(self.target_crs)
        
        # Calcular matriz de distancias
        distances = []
        for i, origin in origins_proj.iterrows():
            row_distances = []
            for j, dest in destinations_proj.iterrows():
                distance = origin.geometry.distance(dest.geometry)
                row_distances.append(distance)
            distances.append(row_distances)
        
        return pd.DataFrame(distances)
    
    def find_nearest_facilities(
        self,
        user_location: Tuple[float, float],
        facilities: List[Dict[str, Any]],
        max_distance: float = 5000,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Encontrar equipamientos más cercanos"""
        user_lat, user_lon = user_location
        user_point = Point(user_lon, user_lat)
        
        # Proyectar punto del usuario
        user_projected = transform(self.to_projected, user_point)
        
        # Calcular distancias
        facilities_with_distance = []
        for facility in facilities:
            facility_point = Point(facility['lon'], facility['lat'])
            facility_projected = transform(self.to_projected, facility_point)
            
            distance = user_projected.distance(facility_projected)
            
            if distance <= max_distance:
                facility_copy = facility.copy()
                facility_copy['distance_meters'] = round(distance, 1)
                facilities_with_distance.append(facility_copy)
        
        # Ordenar por distancia y limitar
        facilities_with_distance.sort(key=lambda x: x['distance_meters'])
        return facilities_with_distance[:limit]
    
    def calculate_service_area(
        self,
        facilities: List[Tuple[float, float]],
        service_radius: float
    ) -> Polygon:
        """Calcular área de servicio combinada de múltiples equipamientos"""
        if not facilities:
            return None
        
        # Crear buffers individuales
        buffers = []
        for lat, lon in facilities:
            buffer_poly = self.create_buffer(lat, lon, service_radius)
            buffers.append(buffer_poly)
        
        # Unir todos los buffers
        from shapely.ops import unary_union
        combined_area = unary_union(buffers)
        
        return combined_area
    
    def analyze_coverage(
        self,
        population_areas: gpd.GeoDataFrame,
        service_area: Polygon
    ) -> Dict[str, Any]:
        """Analizar cobertura de servicio sobre áreas poblacionales"""
        if service_area is None:
            return {
                'total_population': 0,
                'covered_population': 0,
                'coverage_percentage': 0,
                'covered_areas': 0,
                'total_areas': len(population_areas)
            }
        
        # Verificar intersecciones
        population_areas['has_coverage'] = population_areas.geometry.intersects(service_area)
        
        # Calcular cobertura parcial
        population_areas['coverage_ratio'] = population_areas.geometry.apply(
            lambda geom: geom.intersection(service_area).area / geom.area
            if geom.intersects(service_area) else 0
        )
        
        # Calcular estadísticas
        total_pop = population_areas['poblacion'].sum() if 'poblacion' in population_areas.columns else 0
        covered_pop = population_areas[population_areas['has_coverage']]['poblacion'].sum() if 'poblacion' in population_areas.columns else 0
        
        coverage_stats = {
            'total_population': int(total_pop),
            'covered_population': int(covered_pop),
            'coverage_percentage': round((covered_pop / total_pop * 100) if total_pop > 0 else 0, 2),
            'covered_areas': int(population_areas['has_coverage'].sum()),
            'total_areas': len(population_areas),
            'average_coverage_ratio': round(population_areas['coverage_ratio'].mean(), 3)
        }
        
        return coverage_stats
