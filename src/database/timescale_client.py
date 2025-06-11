"""Cliente TimescaleDB para series temporales y análisis IoT"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import asyncpg
from contextlib import asynccontextmanager

from config import settings

logger = logging.getLogger(__name__)

class TimescaleClient:
    """Cliente especializado para TimescaleDB con operaciones de series temporales"""
    
    def __init__(self):
        self._connection_pool = None
        
    async def initialize(self):
        """Inicializar pool de conexiones TimescaleDB"""
        try:
            self._connection_pool = await asyncpg.create_pool(
                settings.database.url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            
            # Verificar que TimescaleDB está disponible
            await self._verify_timescaledb()
            
            logger.info("Cliente TimescaleDB inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando TimescaleDB: {e}")
            raise
    
    async def close(self):
        """Cerrar conexiones"""
        if self._connection_pool:
            await self._connection_pool.close()
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager para obtener conexión del pool"""
        async with self._connection_pool.acquire() as connection:
            yield connection
    
    async def _verify_timescaledb(self):
        """Verificar que TimescaleDB está instalado y funcionando"""
        async with self.get_connection() as conn:
            try:
                # Verificar extensión TimescaleDB
                result = await conn.fetchval(
                    "SELECT extname FROM pg_extension WHERE extname = 'timescaledb'"
                )
                
                if not result:
                    raise RuntimeError("Extensión TimescaleDB no encontrada")
                
                # Verificar versión
                version = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
                logger.info(f"TimescaleDB versión {version} detectada")
                
                return True
                
            except Exception as e:
                logger.error(f"Error verificando TimescaleDB: {e}")
                raise
    
    async def create_hypertable(self, table_name: str, time_column: str, 
                               chunk_time_interval: str = None) -> bool:
        """Crear hypertable para series temporales"""
        try:
            chunk_interval = chunk_time_interval or settings.database.chunk_time_interval
            
            async with self.get_connection() as conn:
                # Verificar si ya es hypertable
                is_hypertable = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM timescaledb_information.hypertables 
                        WHERE hypertable_name = $1
                    )
                    """,
                    table_name
                )
                
                if is_hypertable:
                    logger.info(f"Tabla {table_name} ya es hypertable")
                    return True
                
                # Crear hypertable
                await conn.execute(
                    f"SELECT create_hypertable('{table_name}', '{time_column}', chunk_time_interval => INTERVAL '{chunk_interval}')"
                )
                
                logger.info(f"Hypertable {table_name} creada con intervalo {chunk_interval}")
                return True
                
        except Exception as e:
            logger.error(f"Error creando hypertable {table_name}: {e}")
            return False
    
    async def insert_sensor_reading(self, sensor_id: str, reading_type: str, 
                                   value: float, timestamp: datetime = None,
                                   metadata: Dict[str, Any] = None) -> bool:
        """Insertar lectura de sensor"""
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            async with self.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO sensor_readings (sensor_id, reading_type, value, timestamp, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    sensor_id, reading_type, value, timestamp, metadata or {}
                )
                
            return True
            
        except Exception as e:
            logger.error(f"Error insertando lectura de sensor: {e}")
            return False
    
    async def get_sensor_data(self, sensor_id: str = None, reading_type: str = None,
                             start_time: datetime = None, end_time: datetime = None,
                             limit: int = 1000) -> List[Dict[str, Any]]:
        """Obtener datos de sensores con filtros"""
        try:
            # Construir query con filtros dinámicos
            conditions = []
            params = []
            param_count = 0
            
            if sensor_id:
                param_count += 1
                conditions.append(f"sensor_id = ${param_count}")
                params.append(sensor_id)
            
            if reading_type:
                param_count += 1
                conditions.append(f"reading_type = ${param_count}")
                params.append(reading_type)
            
            if start_time:
                param_count += 1
                conditions.append(f"timestamp >= ${param_count}")
                params.append(start_time)
            
            if end_time:
                param_count += 1
                conditions.append(f"timestamp <= ${param_count}")
                params.append(end_time)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
                SELECT sensor_id, reading_type, value, timestamp, metadata
                FROM sensor_readings
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *params)
                
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores: {e}")
            return []
    
    async def get_hourly_aggregates(self, sensor_id: str = None, reading_type: str = None,
                                   start_time: datetime = None, end_time: datetime = None) -> List[Dict[str, Any]]:
        """Obtener agregados horarios usando continuous aggregates"""
        try:
            conditions = []
            params = []
            param_count = 0
            
            if sensor_id:
                param_count += 1
                conditions.append(f"sensor_id = ${param_count}")
                params.append(sensor_id)
            
            if reading_type:
                param_count += 1
                conditions.append(f"reading_type = ${param_count}")
                params.append(reading_type)
            
            if start_time:
                param_count += 1
                conditions.append(f"hour >= ${param_count}")
                params.append(start_time)
            
            if end_time:
                param_count += 1
                conditions.append(f"hour <= ${param_count}")
                params.append(end_time)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
                SELECT hour, sensor_id, reading_type, 
                       avg_value, min_value, max_value, readings_count
                FROM sensor_readings_hourly
                {where_clause}
                ORDER BY hour DESC
                LIMIT 1000
            """
            
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *params)
                
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error obteniendo agregados horarios: {e}")
            return []
    
    async def detect_anomalies(self, sensor_id: str, reading_type: str,
                              threshold_multiplier: float = 2.0,
                              time_window_hours: int = 24) -> List[Dict[str, Any]]:
        """Detectar anomalías en lecturas de sensores"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_window_hours)
            
            query = """
                WITH stats AS (
                    SELECT 
                        AVG(value) as mean_value,
                        STDDEV(value) as std_value
                    FROM sensor_readings
                    WHERE sensor_id = $1 
                    AND reading_type = $2
                    AND timestamp >= $3
                ),
                anomalies AS (
                    SELECT 
                        sr.*,
                        s.mean_value,
                        s.std_value,
                        ABS(sr.value - s.mean_value) / s.std_value as z_score
                    FROM sensor_readings sr
                    CROSS JOIN stats s
                    WHERE sr.sensor_id = $1 
                    AND sr.reading_type = $2
                    AND sr.timestamp >= $3
                    AND ABS(sr.value - s.mean_value) > (s.std_value * $4)
                )
                SELECT * FROM anomalies
                ORDER BY timestamp DESC
                LIMIT 100
            """
            
            async with self.get_connection() as conn:
                rows = await conn.fetch(
                    query, sensor_id, reading_type, start_time, threshold_multiplier
                )
                
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error detectando anomalías: {e}")
            return []
    
    async def get_sensor_statistics(self, sensor_id: str = None,
                                   time_window_hours: int = 24) -> Dict[str, Any]:
        """Obtener estadísticas de sensores"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_window_hours)
            
            conditions = ["timestamp >= $1", "timestamp <= $2"]
            params = [start_time, end_time]
            
            if sensor_id:
                conditions.append("sensor_id = $3")
                params.append(sensor_id)
            
            where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT 
                    sensor_id,
                    reading_type,
                    COUNT(*) as total_readings,
                    AVG(value) as avg_value,
                    MIN(value) as min_value,
                    MAX(value) as max_value,
                    STDDEV(value) as std_value,
                    MIN(timestamp) as first_reading,
                    MAX(timestamp) as last_reading
                FROM sensor_readings
                {where_clause}
                GROUP BY sensor_id, reading_type
                ORDER BY sensor_id, reading_type
            """
            
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *params)
                
            # Organizar por sensor_id
            stats = {}
            for row in rows:
                sensor_id = row['sensor_id']
                if sensor_id not in stats:
                    stats[sensor_id] = {
                        'sensor_id': sensor_id,
                        'readings': {},
                        'total_readings': 0,
                        'first_reading': row['first_reading'],
                        'last_reading': row['last_reading']