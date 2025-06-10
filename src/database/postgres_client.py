"""Cliente PostgreSQL con soporte para datos geoespaciales"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager
import asyncio
import asyncpg
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely import wkt
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import settings

logger = logging.getLogger(__name__)

class PostgreSQLClient:
    """Cliente PostgreSQL con capacidades GIS"""
    
    def __init__(self):
        self.sync_engine = None
        self.async_engine = None
        self.async_session_factory = None
        self._connection_pool = None
        
    async def initialize(self):
        """Inicializar conexiones a PostgreSQL"""
        try:
            # Motor síncrono para pandas/geopandas
            self.sync_engine = create_engine(
                settings.database.url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            # Motor asíncrono para operaciones async
            self.async_engine = create_async_engine(
                settings.database.async_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            # Factory de sesiones asíncronas
            self.async_session_factory = sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Pool de conexiones asyncpg para operaciones específicas
            self._connection_pool = await asyncpg.create_pool(
                settings.database.url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            
            logger.info("Cliente PostgreSQL inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando PostgreSQL: {e}")
            raise
    
    async def close(self):
        """Cerrar conexiones"""
        if self._connection_pool:
            await self._connection_pool.close()
        if self.async_engine:
            await self.async_engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager para obtener conexión del pool"""
        async with self._connection_pool.acquire() as connection:
            yield connection
    
    @asynccontextmanager
    async def get_session(self):
        """Context manager para sesiones asíncronas"""
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Ejecutar consulta y devolver resultados como lista de diccionarios"""
        async with self.get_connection() as conn:
            try:
                if params:
                    result = await conn.fetch(query, *params.values())
                else:
                    result = await conn.fetch(query)
                
                return [dict(row) for row in result]
            
            except Exception as e:
                logger.error(f"Error ejecutando consulta: {e}")
                raise
    
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> str:
        """Ejecutar comando (INSERT, UPDATE, DELETE)"""
        async with self.get_connection() as conn:
            try:
                if params:
                    result = await conn.execute(command, *params.values())
                else:
                    result = await conn.execute(command)
                
                return result
            
            except Exception as e:
                logger.error(f"Error ejecutando comando: {e}")
                raise
    
    def read_geodataframe(self, query: str, geom_col: str = 'geom') -> gpd.GeoDataFrame:
        """Leer datos geoespaciales como GeoDataFrame"""
        try:
            # Leer con geopandas
            gdf = gpd.read_postgis(
                query,
                self.sync_engine,
                geom_col=geom_col,
                crs=settings.gis.default_crs
            )
            
            logger.info(f"Leídos {len(gdf)} registros geoespaciales")
            return gdf
            
        except Exception as e:
            logger.error(f"Error leyendo GeoDataFrame: {e}")
            raise
    
    async def get_census_sections(self, bounds: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """Obtener secciones censales con filtro opcional de bbox"""
        
        base_query = """
        SELECT 
            id,
            codigo_seccion,
            codigo_distrito,
            codigo_municipio,
            nombre_municipio,
            poblacion,
            superficie_km2,
            densidad_hab_km2,
            ST_AsText(geom) as geometry,
            ST_X(ST_Centroid(geom)) as centroid_lon,
            ST_Y(ST_Centroid(geom)) as centroid_lat
        FROM secciones_censales
        """
        
        if bounds:
            # Agregar filtro espacial
            xmin, ymin, xmax, ymax = bounds
            bbox_filter = f"""
            WHERE ST_Intersects(
                geom,
                ST_MakeEnvelope({xmin}, {ymin}, {xmax}, {ymax}, 4326)
            )
            """
            query = base_query + bbox_filter
        else:
            query = base_query
        
        try:
            # Ejecutar consulta
            async with self.get_connection() as conn:
                rows = await conn.fetch(query)
            
            # Convertir a GeoDataFrame
            data = []
            for row in rows:
                row_dict = dict(row)
                # Convertir WKT a geometría
                geom_wkt = row_dict.pop('geometry')
                row_dict['geometry'] = wkt.loads(geom_wkt)
                data.append(row_dict)
            
            if data:
                gdf = gpd.GeoDataFrame(data, crs=settings.gis.default_crs)
                logger.info(f"Obtenidas {len(gdf)} secciones censales")
                return gdf
            else:
                logger.warning("No se encontraron secciones censales")
                return gpd.GeoDataFrame()
                
        except Exception as e:
            logger.error(f"Error obteniendo secciones censales: {e}")
            raise
    
    async def spatial_join_facilities_sections(
        self, 
        facilities: List[Dict[str, Any]], 
        buffer_meters: int = 0
    ) -> List[Dict[str, Any]]:
        """Realizar join espacial entre equipamientos y secciones censales"""
        
        if not facilities:
            return []
        
        # Crear puntos de equipamientos para la consulta
        facility_points = []
        for i, facility in enumerate(facilities):
            facility_points.append({
                'id': i,
                'lat': facility['lat'],
                'lon': facility['lon'],
                'name': facility['name'],
                'type': facility.get('type', 'unknown'),
                'distance': facility.get('distance', 0)
            })
        
        # Construir consulta espacial
        values_clause = ",".join([
            f"({fp['id']}, {fp['lat']}, {fp['lon']}, '{fp['name']}', '{fp['type']}', {fp['distance']})"
            for fp in facility_points
        ])
        
        query = f"""
        WITH facilities AS (
            SELECT 
                id,
                lat,
                lon,
                name,
                type,
                distance,
                ST_SetSRID(ST_MakePoint(lon, lat), 4326) as geom_point
            FROM (VALUES {values_clause}) AS f(id, lat, lon, name, type, distance)
        ),
        buffered_facilities AS (
            SELECT 
                *,
                CASE 
                    WHEN {buffer_meters} > 0 THEN ST_Buffer(geom_point::geography, {buffer_meters})::geometry
                    ELSE geom_point
                END as geom_buffer
            FROM facilities
        )
        SELECT 
            f.id as facility_id,
            f.name as facility_name,
            f.type as facility_type,
            f.lat,
            f.lon,
            f.distance,
            s.codigo_seccion,
            s.codigo_distrito,
            s.codigo_municipio,
            s.nombre_municipio,
            s.poblacion,
            s.superficie_km2,
            s.densidad_hab_km2,
            ST_Distance(f.geom_point::geography, s.geom::geography) as distance_to_section_meters
        FROM buffered_facilities f
        JOIN secciones_censales s ON ST_Intersects(f.geom_buffer, s.geom)
        ORDER BY f.id, distance_to_section_meters
        """
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query)
            
            # Convertir a lista de diccionarios
            results = [dict(row) for row in rows]
            
            logger.info(f"Join espacial completado: {len(results)} intersecciones encontradas")
            return results
            
        except Exception as e:
            logger.error(f"Error en join espacial: {e}")
            raise
    
    async def get_section_statistics(self, section_codes: List[str]) -> List[Dict[str, Any]]:
        """Obtener estadísticas de secciones censales específicas"""
        
        if not section_codes:
            return []
        
        # Crear lista de códigos para la consulta
        codes_str = "','".join(section_codes)
        
        query = f"""
        SELECT 
            codigo_seccion,
            codigo_distrito,
            codigo_municipio,
            nombre_municipio,
            poblacion,
            superficie_km2,
            densidad_hab_km2,
            ST_Area(geom::geography) / 1000000 as area_real_km2,
            ST_X(ST_Centroid(geom)) as centroid_lon,
            ST_Y(ST_Centroid(geom)) as centroid_lat
        FROM secciones_censales
        WHERE codigo_seccion IN ('{codes_str}')
        ORDER BY codigo_seccion
        """
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query)
            
            results = [dict(row) for row in rows]
            logger.info(f"Estadísticas obtenidas para {len(results)} secciones")
            return results
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de secciones: {e}")
            raise
    
    async def analyze_facility_coverage(
        self, 
        facility_type: str, 
        max_distance_meters: int = 1000
    ) -> Dict[str, Any]:
        """Analizar cobertura de un tipo de equipamiento por secciones censales"""
        
        query = f"""
        WITH facility_buffers AS (
            SELECT 
                ST_Union(ST_Buffer(geom::geography, {max_distance_meters}))::geometry as coverage_geom
            FROM equipamientos 
            WHERE tipo = '{facility_type}'
        ),
        section_coverage AS (
            SELECT 
                s.codigo_seccion,
                s.nombre_municipio,
                s.poblacion,
                s.superficie_km2,
                CASE 
                    WHEN ST_Intersects(s.geom, fb.coverage_geom) THEN true
                    ELSE false
                END as tiene_cobertura,
                CASE 
                    WHEN ST_Intersects(s.geom, fb.coverage_geom) THEN 
                        ST_Area(ST_Intersection(s.geom, fb.coverage_geom)::geography) / ST_Area(s.geom::geography)
                    ELSE 0
                END as porcentaje_cobertura
            FROM secciones_censales s
            CROSS JOIN facility_buffers fb
        )
        SELECT 
            COUNT(*) as total_secciones,
            COUNT(*) FILTER (WHERE tiene_cobertura) as secciones_con_cobertura,
            ROUND(
                COUNT(*) FILTER (WHERE tiene_cobertura)::numeric / COUNT(*)::numeric * 100, 2
            ) as porcentaje_secciones_cubiertas,
            SUM(poblacion) as poblacion_total,
            SUM(poblacion) FILTER (WHERE tiene_cobertura) as poblacion_cubierta,
            ROUND(
                SUM(poblacion) FILTER (WHERE tiene_cobertura)::numeric / SUM(poblacion)::numeric * 100, 2
            ) as porcentaje_poblacion_cubierta,
            AVG(porcentaje_cobertura) FILTER (WHERE tiene_cobertura) as cobertura_promedio
        FROM section_coverage
        """
        
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query)
            
            result = dict(row) if row else {}
            logger.info(f"Análisis de cobertura completado para {facility_type}")
            return result
            
        except Exception as e:
            logger.error(f"Error analizando cobertura: {e}")
            raise

# Instancia global del cliente
postgres_client = PostgreSQLClient()