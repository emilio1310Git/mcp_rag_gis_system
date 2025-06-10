"""Servicio GIS con análisis geoespacial y PostgreSQL"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import folium
from folium import plugins
import pyproj
from functools import partial

from config import settings
from database import postgres_client

logger = logging.getLogger(__name__)

class GISService:
    """Servicio para análisis geoespacial y manejo de secciones censales"""
    
    def __init__(self):
        self.postgres_client = postgres_client
        self.transformer_to_projected = None
        self.transformer_to_geographic = None
        self._setup_projections()
    
    def _setup_projections(self):
        """Configurar transformadores de proyección"""
        try:
            # Transformador de geográfico a proyectado (para cálculos de distancia)

            self.transformer_to_projected = pyproj.Transformer.from_crs(
                settings.gis.default_crs,
                settings.gis.projected_crs,
                always_xy=True
            )
        except Exception as e:
            logger.error(f"Error configurando proyecciones: {e}")
            # Configuración fallback
            self.transformer_to_projected = None
            self.transformer_to_geographic = None        
        try:
            # Transformador de proyectado a geográfico
            self.transformer_to_geographic = pyproj.Transformer.from_crs(
                settings.gis.projected_crs,
                settings.gis.default_crs,
                always_xy=True
            )
            
        except Exception as e:
            logger.error(f"Error configurando proyecciones: {e}")
    
    async def get_census_sections(
        self, 
        bounds: Optional[Tuple[float, float, float, float]] = None,
        municipio: Optional[str] = None
    ) -> gpd.GeoDataFrame:
        """Obtener secciones censales con filtros opcionales"""
        try:
            # Construir filtros adicionales
            additional_filters = []
            
            if municipio:
                additional_filters.append(f"nombre_municipio ILIKE '%{municipio}%'")
            
            # Obtener secciones de PostgreSQL
            sections = await self.postgres_client.get_census_sections(bounds)
            
            # Aplicar filtros adicionales si es necesario
            if additional_filters and not sections.empty:
                filter_query = " AND ".join(additional_filters)
                sections = sections.query(filter_query)
            
            logger.info(f"Obtenidas {len(sections)} secciones censales")
            return sections
            
        except Exception as e:
            logger.error(f"Error obteniendo secciones censales: {e}")
            return gpd.GeoDataFrame()
    
    async def spatial_join_facilities_sections(
        self,
        facilities: List[Dict[str, Any]],
        buffer_meters: int = 0,
        analysis_type: str = "intersects"
    ) -> List[Dict[str, Any]]:
        """
        Realizar join espacial entre equipamientos y secciones censales
        
        Args:
            facilities: Lista de equipamientos con lat/lon
            buffer_meters: Buffer en metros alrededor de equipamientos
            analysis_type: Tipo de análisis ('intersects', 'within', 'contains')
        """
        try:
            if not facilities:
                return []
            
            # Usar cliente PostgreSQL para análisis espacial
            results = await self.postgres_client.spatial_join_facilities_sections(
                facilities, buffer_meters
            )
            
            # Enriquecer resultados con análisis adicionales
            enriched_results = []
            for result in results:
                enriched_result = result.copy()
                
                # Calcular métricas adicionales
                enriched_result['equipamientos_por_mil_hab'] = (
                    1000 / result['poblacion'] if result['poblacion'] > 0 else 0
                )
                
                enriched_result['densidad_categoria'] = self._classify_density(
                    result['densidad_hab_km2']
                )
                
                enriched_result['accesibilidad_score'] = self._calculate_accessibility_score(
                    result['distance_to_section_meters'],
                    result['facility_type']
                )
                
                enriched_results.append(enriched_result)
            
            logger.info(f"Join espacial completado: {len(enriched_results)} intersecciones")
            return enriched_results
            
        except Exception as e:
            logger.error(f"Error en join espacial: {e}")
            raise
    
    def _classify_density(self, density: float) -> str:
        """Clasificar densidad poblacional"""
        if density < 100:
            return "muy_baja"
        elif density < 500:
            return "baja"
        elif density < 2000:
            return "media"
        elif density < 5000:
            return "alta"
        else:
            return "muy_alta"
    
    def _calculate_accessibility_score(self, distance_meters: float, facility_type: str) -> float:
        """Calcular score de accesibilidad basado en distancia y tipo"""
        # Distancias ideales por tipo de equipamiento (en metros)
        ideal_distances = {
            'hospital': 2000,
            'school': 800,
            'pharmacy': 500,
            'police': 1500,
            'fire_station': 3000,
            'library': 1000,
            'post_office': 1000,
            'bank': 800
        }
        
        ideal_distance = ideal_distances.get(facility_type, 1000)
        
        # Score inversamente proporcional a la distancia
        if distance_meters <= ideal_distance:
            return 100.0
        else:
            # Decae exponencialmente después de la distancia ideal
            return max(0, 100 * (ideal_distance / distance_meters) ** 0.5)
    
    async def analyze_facility_coverage(
        self,
        facility_type: str,
        max_distance_meters: int = 1000,
        municipio: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analizar cobertura de equipamientos por secciones censales"""
        try:
            # Usar análisis de cobertura de PostgreSQL
            coverage_stats = await self.postgres_client.analyze_facility_coverage(
                facility_type, max_distance_meters
            )
            
            # Enriquecer con análisis adicionales
            if coverage_stats:
                coverage_stats['calificacion_cobertura'] = self._classify_coverage(
                    coverage_stats.get('porcentaje_poblacion_cubierta', 0)
                )
                
                coverage_stats['recomendaciones'] = self._generate_coverage_recommendations(
                    coverage_stats, facility_type
                )
            
            return coverage_stats
            
        except Exception as e:
            logger.error(f"Error analizando cobertura: {e}")
            raise
    
    def _classify_coverage(self, coverage_percentage: float) -> str:
        """Clasificar nivel de cobertura"""
        if coverage_percentage >= 90:
            return "excelente"
        elif coverage_percentage >= 75:
            return "buena"
        elif coverage_percentage >= 50:
            return "regular"
        elif coverage_percentage >= 25:
            return "deficiente"
        else:
            return "muy_deficiente"
    
    def _generate_coverage_recommendations(
        self, 
        coverage_stats: Dict[str, Any], 
        facility_type: str
    ) -> List[str]:
        """Generar recomendaciones basadas en análisis de cobertura"""
        recommendations = []
        
        coverage_pct = coverage_stats.get('porcentaje_poblacion_cubierta', 0)
        
        if coverage_pct < 50:
            recommendations.append(
                f"Se necesita aumentar significativamente el número de {facility_type}s"
            )
        
        if coverage_pct < 75:
            recommendations.append(
                "Considerar ubicaciones estratégicas en zonas no cubiertas"
            )
        
        if coverage_stats.get('cobertura_promedio', 0) < 0.7:
            recommendations.append(
                "Optimizar ubicaciones existentes para mejorar cobertura parcial"
            )
        
        return recommendations
    
    async def find_optimal_locations(
        self,
        facility_type: str,
        num_locations: int = 3,
        population_weight: float = 0.7,
        coverage_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Encontrar ubicaciones óptimas para nuevos equipamientos
        usando análisis de máxima cobertura ponderada
        """
        try:
            # Obtener secciones censales sin cobertura o con cobertura deficiente
            uncovered_query = f"""
            SELECT DISTINCT
                s.codigo_seccion,
                s.poblacion,
                s.densidad_hab_km2,
                ST_X(ST_Centroid(s.geom)) as centroid_lon,
                ST_Y(ST_Centroid(s.geom)) as centroid_lat,
                ST_AsText(ST_Centroid(s.geom)) as centroid_wkt
            FROM secciones_censales s
            WHERE NOT EXISTS (
                SELECT 1 FROM equipamientos e
                WHERE e.tipo = '{facility_type}'
                AND ST_DWithin(s.geom::geography, e.geom::geography, 1000)
            )
            ORDER BY s.poblacion DESC, s.densidad_hab_km2 DESC
            LIMIT {num_locations * 3}
            """
            
            results = await self.postgres_client.execute_query(uncovered_query)
            
            if not results:
                return []
            
            # Calcular scores para cada ubicación potencial
            optimal_locations = []
            for result in results[:num_locations]:
                location_score = (
                    result['poblacion'] * population_weight +
                    result['densidad_hab_km2'] * coverage_weight
                )
                
                optimal_location = {
                    'codigo_seccion': result['codigo_seccion'],
                    'lat': result['centroid_lat'],
                    'lon': result['centroid_lon'],
                    'poblacion_servida': result['poblacion'],
                    'densidad': result['densidad_hab_km2'],
                    'score_ubicacion': round(location_score, 2),
                    'justificacion': self._generate_location_justification(result, facility_type)
                }
                
                optimal_locations.append(optimal_location)
            
            logger.info(f"Encontradas {len(optimal_locations)} ubicaciones óptimas")
            return optimal_locations
            
        except Exception as e:
            logger.error(f"Error encontrando ubicaciones óptimas: {e}")
            raise
    
    def _generate_location_justification(
        self, 
        location_data: Dict[str, Any], 
        facility_type: str
    ) -> str:
        """Generar justificación para ubicación propuesta"""
        justifications = []
        
        if location_data['poblacion'] > 1000:
            justifications.append(f"Alta población ({location_data['poblacion']} habitantes)")
        
        if location_data['densidad_hab_km2'] > 2000:
            justifications.append(f"Alta densidad poblacional ({location_data['densidad_hab_km2']:.0f} hab/km²)")
        
        justifications.append("Sin cobertura actual del servicio")
        
        return "; ".join(justifications)
    
    async def create_coverage_map(
        self,
        facility_type: str,
        center_lat: float,
        center_lon: float,
        zoom_level: int = 12,
        show_sections: bool = True,
        show_facilities: bool = True
    ) -> str:
        """Crear mapa de cobertura de equipamientos"""
        try:
            # Crear mapa base
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=zoom_level,
                tiles='OpenStreetMap'
            )
            
            # Obtener secciones censales en el área
            bbox = self._calculate_bbox(center_lat, center_lon, 0.02)  # ~2km aprox
            sections = await self.get_census_sections(bbox)
            
            if show_sections and not sections.empty:
                # Añadir secciones censales con coloración por densidad
                self._add_sections_to_map(m, sections)
            
            if show_facilities:
                # Obtener equipamientos del tipo especificado
                facilities_query = f"""
                SELECT 
                    nombre,
                    tipo,
                    ST_X(geom) as lon,
                    ST_Y(geom) as lat,
                    direccion,
                    telefono
                FROM equipamientos
                WHERE tipo = '{facility_type}'
                AND ST_DWithin(
                    geom::geography,
                    ST_MakePoint({center_lon}, {center_lat})::geography,
                    5000
                )
                """
                
                facilities = await self.postgres_client.execute_query(facilities_query)
                
                # Añadir equipamientos al mapa
                self._add_facilities_to_map(m, facilities, facility_type)
            
            # Añadir controles del mapa
            folium.LayerControl().add_to(m)
            
            # Guardar mapa
            map_filename = f"cobertura_{facility_type}_{center_lat}_{center_lon}.html"
            map_path = settings.paths.maps_dir / map_filename
            m.save(str(map_path))
            
            logger.info(f"Mapa de cobertura creado: {map_filename}")
            return map_filename
            
        except Exception as e:
            logger.error(f"Error creando mapa de cobertura: {e}")
            raise
    
    def _calculate_bbox(
        self, 
        center_lat: float, 
        center_lon: float, 
        delta: float
    ) -> Tuple[float, float, float, float]:
        """Calcular bounding box alrededor de un punto"""
        return (
            center_lon - delta,  # xmin
            center_lat - delta,  # ymin
            center_lon + delta,  # xmax
            center_lat + delta   # ymax
        )
    
    def _add_sections_to_map(self, map_obj: folium.Map, sections: gpd.GeoDataFrame):
        """Añadir secciones censales al mapa con coloración por densidad"""
        # Crear colormap para densidad poblacional
        colormap = folium.LinearColormap(
            colors=['yellow', 'orange', 'red', 'darkred'],
            vmin=sections['densidad_hab_km2'].min(),
            vmax=sections['densidad_hab_km2'].max(),
            caption='Densidad poblacional (hab/km²)'
        )
        
        # Añadir cada sección como polígono
        for idx, section in sections.iterrows():
            popup_html = f"""
            <div style="width:200px">
                <h4>Sección Censal</h4>
                <p><b>Código:</b> {section['codigo_seccion']}</p>
                <p><b>Municipio:</b> {section['nombre_municipio']}</p>
                <p><b>Población:</b> {section['poblacion']:,}</p>
                <p><b>Densidad:</b> {section['densidad_hab_km2']:.1f} hab/km²</p>
                <p><b>Superficie:</b> {section['superficie_km2']:.2f} km²</p>
            </div>
            """
            
            folium.GeoJson(
                section['geometry'],
                style_function=lambda x, density=section['densidad_hab_km2']: {
                    'fillColor': colormap(density),
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.6
                },
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"Sección {section['codigo_seccion']} - {section['poblacion']:,} hab"
            ).add_to(map_obj)
        
        # Añadir colormap al mapa
        colormap.add_to(map_obj)
    
    def _add_facilities_to_map(
        self, 
        map_obj: folium.Map, 
        facilities: List[Dict[str, Any]], 
        facility_type: str
    ):
        """Añadir equipamientos al mapa"""
        facility_config = settings.gis.facility_types.get(facility_type, {
            'icon': 'info-sign',
            'color': 'blue',
            'name': facility_type
        })
        
        for facility in facilities:
            popup_html = f"""
            <div style="width:200px">
                <h4>{facility['nombre']}</h4>
                <p><b>Tipo:</b> {facility_config['name']}</p>
                <p><b>Dirección:</b> {facility.get('direccion', 'No disponible')}</p>
                <p><b>Teléfono:</b> {facility.get('telefono', 'No disponible')}</p>
            </div>
            """
            
            folium.Marker(
                [facility['lat'], facility['lon']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=facility['nombre'],
                icon=folium.Icon(
                    color=facility_config['color'],
                    icon=facility_config['icon'],
                    prefix='fa'
                )
            ).add_to(map_obj)
            
            # Añadir círculo de cobertura (1km de radio)
            folium.Circle(
                [facility['lat'], facility['lon']],
                radius=1000,
                color=facility_config['color'],
                fill=True,
                fillOpacity=0.1,
                weight=2,
                popup=f"Área de cobertura - {facility['nombre']}"
            ).add_to(map_obj)
    
    async def generate_accessibility_report(
        self,
        municipio: str,
        facility_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generar informe completo de accesibilidad a equipamientos"""
        try:
            if facility_types is None:
                facility_types = list(settings.gis.facility_types.keys())
            
            report = {
                'municipio': municipio,
                'fecha_analisis': pd.Timestamp.now().isoformat(),
                'equipamientos_analizados': facility_types,
                'resultados': {}
            }
            
            # Análisis por tipo de equipamiento
            for facility_type in facility_types:
                coverage_analysis = await self.analyze_facility_coverage(
                    facility_type, max_distance_meters=1000
                )
                
                optimal_locations = await self.find_optimal_locations(
                    facility_type, num_locations=3
                )
                
                report['resultados'][facility_type] = {
                    'cobertura': coverage_analysis,
                    'ubicaciones_optimas': optimal_locations,
                    'prioridad': settings.gis.facility_types[facility_type].get('priority', 10)
                }
            
            # Resumen ejecutivo
            report['resumen_ejecutivo'] = self._generate_executive_summary(report)
            
            logger.info(f"Informe de accesibilidad generado para {municipio}")
            return report
            
        except Exception as e:
            logger.error(f"Error generando informe de accesibilidad: {e}")
            raise
    
    def _generate_executive_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generar resumen ejecutivo del informe"""
        summary = {
            'equipamientos_criticos': [],
            'cobertura_promedio': 0,
            'poblacion_total_analizada': 0,
            'recomendaciones_prioritarias': []
        }
        
        total_coverage = 0
        count = 0
        
        for facility_type, results in report['resultados'].items():
            coverage_pct = results['cobertura'].get('porcentaje_poblacion_cubierta', 0)
            total_coverage += coverage_pct
            count += 1
            
            # Identificar equipamientos críticos (cobertura < 50%)
            if coverage_pct < 50:
                summary['equipamientos_criticos'].append({
                    'tipo': facility_type,
                    'cobertura': coverage_pct,
                    'prioridad': results['prioridad']
                })
        
        # Calcular cobertura promedio
        if count > 0:
            summary['cobertura_promedio'] = round(total_coverage / count, 2)
        
        # Ordenar equipamientos críticos por prioridad
        summary['equipamientos_criticos'].sort(key=lambda x: x['prioridad'])
        
        # Generar recomendaciones prioritarias
        if summary['equipamientos_criticos']:
            summary['recomendaciones_prioritarias'] = [
                f"Priorizar mejora de cobertura en {eq['tipo']} (actual: {eq['cobertura']:.1f}%)"
                for eq in summary['equipamientos_criticos'][:3]
            ]
        
        return summary