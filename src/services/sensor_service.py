"""Servicio para gestión de sensores IoT y simulación de datos"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from dataclasses import dataclass

from database.timescale_client import timescale_client
from database.postgres_client import postgres_client
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class SensorInfo:
    """Información de un sensor"""
    sensor_id: str
    name: str
    sensor_type: str
    equipment_id: Optional[str]
    location: Dict[str, float]  # {"lat": float, "lon": float}
    active: bool = True
    metadata: Dict[str, Any] = None

class SensorService:
    """Servicio para gestión completa de sensores IoT"""
    
    def __init__(self):
        self.sensors: Dict[str, SensorInfo] = {}
        self.simulation_task = None
        self.simulation_running = False
        
    async def initialize(self):
        """Inicializar servicio de sensores"""
        try:
            await timescale_client.initialize()
            await self._setup_database_schema()
            await self._load_sensors_from_db()
            
            if settings.sensors.simulation_enabled:
                await self._setup_demo_sensors()
                await self.start_simulation()
            
            logger.info("Servicio de sensores inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando servicio de sensores: {e}")
            raise
    
    async def _setup_database_schema(self):
        """Configurar esquema de base de datos para sensores"""
        try:
            async with timescale_client.get_connection() as conn:
                # Crear tabla de sensores si no existe
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sensors (
                        sensor_id VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        sensor_type VARCHAR(50) NOT NULL,
                        equipment_id UUID REFERENCES equipamientos(id) ON DELETE SET NULL,
                        location GEOMETRY(POINT, 4326) NOT NULL,
                        active BOOLEAN DEFAULT TRUE,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Crear tabla de lecturas de sensores
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        id SERIAL,
                        sensor_id VARCHAR(50) NOT NULL,
                        reading_type VARCHAR(50) NOT NULL,
                        value NUMERIC NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
                    )
                """)
                
                # Crear índices
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sensors_location 
                    ON sensors USING GIST (location)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time 
                    ON sensor_readings (sensor_id, timestamp DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sensor_readings_type_time 
                    ON sensor_readings (reading_type, timestamp DESC)
                """)
                
                # Convertir a hypertable
                await timescale_client.create_hypertable(
                    "sensor_readings", 
                    "timestamp",
                    settings.database.chunk_time_interval
                )
                
                # Crear continuous aggregate para agregados horarios
                await timescale_client.create_continuous_aggregate(
                    "sensor_readings_hourly",
                    "sensor_readings", 
                    "timestamp",
                    "1 hour"
                )
                
            logger.info("Esquema de base de datos de sensores configurado")
            
        except Exception as e:
            logger.error(f"Error configurando esquema de sensores: {e}")
            raise
    
    async def _load_sensors_from_db(self):
        """Cargar sensores existentes desde la base de datos"""
        try:
            async with timescale_client.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT sensor_id, name, sensor_type, equipment_id,
                           ST_X(location) as lon, ST_Y(location) as lat,
                           active, metadata
                    FROM sensors
                    WHERE active = TRUE
                """)
                
                for row in rows:
                    sensor_info = SensorInfo(
                        sensor_id=row['sensor_id'],
                        name=row['name'],
                        sensor_type=row['sensor_type'],
                        equipment_id=row['equipment_id'],
                        location={"lat": row['lat'], "lon": row['lon']},
                        active=row['active'],
                        metadata=row['metadata'] or {}
                    )
                    self.sensors[row['sensor_id']] = sensor_info
                
            logger.info(f"Cargados {len(self.sensors)} sensores desde la base de datos")
            
        except Exception as e:
            logger.error(f"Error cargando sensores: {e}")
    
    async def _setup_demo_sensors(self):
        """Configurar sensores de demostración"""
        try:
            # Obtener equipamientos existentes para asociar sensores
            async with postgres_client.get_connection() as conn:
                equipamientos = await conn.fetch("""
                    SELECT id, nombre, tipo, ST_X(geom) as lon, ST_Y(geom) as lat
                    FROM equipamientos
                    LIMIT 10
                """)
            
            demo_sensors = []
            sensor_types = settings.sensors.supported_types
            
            for i, equip in enumerate(equipamientos):
                # Crear 1-3 sensores por equipamiento
                num_sensors = random.randint(1, 3)
                
                for j in range(num_sensors):
                    sensor_type = random.choice(sensor_types)
                    sensor_id = f"DEMO_{equip['tipo'].upper()}_{i+1}_{sensor_type}_{j+1}"
                    
                    # Añadir pequeña variación a la ubicación
                    lat = equip['lat'] + random.uniform(-0.001, 0.001)
                    lon = equip['lon'] + random.uniform(-0.001, 0.001)
                    
                    sensor_info = SensorInfo(
                        sensor_id=sensor_id,
                        name=f"Sensor {sensor_type} - {equip['nombre']}",
                        sensor_type=sensor_type,
                        equipment_id=str(equip['id']),
                        location={"lat": lat, "lon": lon},
                        metadata={
                            "demo": True,
                            "equipment_name": equip['nombre'],
                            "equipment_type": equip['tipo']
                        }
                    )
                    demo_sensors.append(sensor_info)
            
            # Insertar sensores demo en la base de datos
            for sensor in demo_sensors:
                await self.register_sensor(sensor)
            
            logger.info(f"Configurados {len(demo_sensors)} sensores de demostración")
            
        except Exception as e:
            logger.error(f"Error configurando sensores demo: {e}")
    
    async def register_sensor(self, sensor_info: SensorInfo) -> bool:
        """Registrar un nuevo sensor"""
        try:
            async with timescale_client.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO sensors (sensor_id, name, sensor_type, equipment_id, location, active, metadata)
                    VALUES ($1, $2, $3, $4, ST_Point($5, $6, 4326), $7, $8)
                    ON CONFLICT (sensor_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        sensor_type = EXCLUDED.sensor_type,
                        equipment_id = EXCLUDED.equipment_id,
                        location = EXCLUDED.location,
                        active = EXCLUDED.active,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, 
                sensor_info.sensor_id,
                sensor_info.name,
                sensor_info.sensor_type,
                sensor_info.equipment_id,
                sensor_info.location['lon'],
                sensor_info.location['lat'],
                sensor_info.active,
                json.dumps(sensor_info.metadata or {})
                )
            
            # Añadir a memoria
            self.sensors[sensor_info.sensor_id] = sensor_info
            
            logger.info(f"Sensor {sensor_info.sensor_id} registrado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error registrando sensor {sensor_info.sensor_id}: {e}")
            return False
    
    async def record_reading(self, sensor_id: str, reading_type: str, 
                           value: float, timestamp: datetime = None,
                           metadata: Dict[str, Any] = None) -> bool:
        """Registrar lectura de sensor"""
        try:
            if sensor_id not in self.sensors:
                logger.warning(f"Sensor {sensor_id} no registrado")
                return False
            
            success = await timescale_client.insert_sensor_reading(
                sensor_id, reading_type, value, timestamp, metadata
            )
            
            if success:
                # Verificar si hay alertas
                await self._check_alerts(sensor_id, reading_type, value)
            
            return success
            
        except Exception as e:
            logger.error(f"Error registrando lectura: {e}")
            return False
    
    async def _check_alerts(self, sensor_id: str, reading_type: str, value: float):
        """Verificar si una lectura genera alertas"""
        try:
            thresholds = settings.sensors.default_thresholds.get(reading_type, {})
            
            if not thresholds:
                return
            
            sensor_info = self.sensors.get(sensor_id)
            if not sensor_info:
                return
            
            alert_level = None
            message = None
            
            # Verificar umbrales críticos
            if 'critical' in thresholds and value >= thresholds['critical']:
                alert_level = "CRITICAL"
                message = f"Valor crítico en {sensor_info.name}: {value} (umbral: {thresholds['critical']})"
            
            # Verificar umbrales máximos
            elif 'max' in thresholds and value > thresholds['max']:
                alert_level = "WARNING"
                message = f"Valor alto en {sensor_info.name}: {value} (máximo: {thresholds['max']})"
            
            # Verificar umbrales mínimos
            elif 'min' in thresholds and value < thresholds['min']:
                alert_level = "WARNING"
                message = f"Valor bajo en {sensor_info.name}: {value} (mínimo: {thresholds['min']})"
            
            if alert_level and message:
                await self._trigger_alert(sensor_id, reading_type, value, alert_level, message)
            
        except Exception as e:
            logger.error(f"Error verificando alertas: {e}")
    
    async def _trigger_alert(self, sensor_id: str, reading_type: str, value: float,
                           level: str, message: str):
        """Disparar alerta"""
        try:
            # Registrar alerta en logs
            logger.warning(f"ALERTA {level}: {message}")
            
            # Aquí se podría integrar con sistema de notificaciones
            # Por ejemplo, enviar SMS via Twilio, email, etc.
            
            alert_data = {
                "sensor_id": sensor_id,
                "reading_type": reading_type,
                "value": value,
                "level": level,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Guardar alerta en base de datos (opcional)
            async with timescale_client.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO sensor_alerts (sensor_id, reading_type, value, level, message, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                """, sensor_id, reading_type, value, level, message, datetime.now())
            
        except Exception as e:
            logger.error(f"Error disparando alerta: {e}")
    
    async def start_simulation(self):
        """Iniciar simulación de datos de sensores"""
        if self.simulation_running:
            logger.warning("Simulación ya está corriendo")
            return
        
        self.simulation_running = True
        self.simulation_task = asyncio.create_task(self._simulation_loop())
        logger.info("Simulación de sensores iniciada")
    
    async def stop_simulation(self):
        """Detener simulación de datos"""
        self.simulation_running = False
        if self.simulation_task:
            self.simulation_task.cancel()
            try:
                await self.simulation_task
            except asyncio.CancelledError:
                pass
        logger.info("Simulación de sensores detenida")
    
    async def _simulation_loop(self):
        """Bucle principal de simulación"""
        try:
            while self.simulation_running:
                # Simular lecturas para todos los sensores activos
                tasks = []
                for sensor_info in self.sensors.values():
                    if sensor_info.active:
                        task = self._simulate_sensor_reading(sensor_info)
                        tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Esperar intervalo de simulación
                await asyncio.sleep(settings.sensors.simulation_interval)
                
        except asyncio.CancelledError:
            logger.info("Simulación cancelada")
        except Exception as e:
            logger.error(f"Error en simulación: {e}")
    
    async def _simulate_sensor_reading(self, sensor_info: SensorInfo):
        """Simular lectura individual de sensor"""
        try:
            # Generar valor basado en el tipo de sensor
            value = self._generate_realistic_value(sensor_info.sensor_type)
            
            # Registrar lectura
            await self.record_reading(
                sensor_info.sensor_id,
                sensor_info.sensor_type,
                value,
                datetime.now(),
                {"simulated": True}
            )
            
        except Exception as e:
            logger.error(f"Error simulando lectura para {sensor_info.sensor_id}: {e}")
    
    def _generate_realistic_value(self, sensor_type: str) -> float:
        """Generar valores realistas según el tipo de sensor"""
        base_values = {
            "temperature": {"base": 22, "variation": 8, "trend": 0.1},
            "humidity": {"base": 60, "variation": 20, "trend": 0.05},
            "air_quality": {"base": 50, "variation": 30, "trend": 0.2},
            "noise": {"base": 45, "variation": 15, "trend": 0.15},
            "occupancy": {"base": 30, "variation": 40, "trend": 0.3}
        }
        
        config = base_values.get(sensor_type, {"base": 50, "variation": 10, "trend": 0.1})
        
        # Valor base con variación aleatoria
        base = config["base"]
        variation = config["variation"]
        trend = config["trend"]
        
        # Añadir variación temporal (simular ciclos diarios, etc.)
        hour = datetime.now().hour
        daily_factor = 1 + 0.3 * abs(12 - hour) / 12  # Mayor variación lejos del mediodía
        
        # Generar valor con distribución normal
        value = base + random.normalvariate(0, variation * daily_factor * trend)
        
        # Asegurar valores positivos y dentro de rangos lógicos
        if sensor_type == "humidity":
            value = max(0, min(100, value))
        elif sensor_type == "occupancy":
            value = max(0, value)
        elif sensor_type == "temperature":
            value = max(-50, min(80, value))
        else:
            value = max(0, value)
        
        return round(value, 2)
    
    async def get_sensors_list(self) -> List[Dict[str, Any]]:
        """Obtener lista de sensores registrados"""
        sensors_list = []
        for sensor_info in self.sensors.values():
            sensors_list.append({
                "sensor_id": sensor_info.sensor_id,
                "name": sensor_info.name,
                "sensor_type": sensor_info.sensor_type,
                "equipment_id": sensor_info.equipment_id,
                "location": sensor_info.location,
                "active": sensor_info.active,
                "metadata": sensor_info.metadata
            })
        return sensors_list
    
    async def get_sensor_data(self, sensor_id: str = None, 
                            reading_type: str = None,
                            hours: int = 24) -> Dict[str, Any]:
        """Obtener datos de sensores con filtros"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        return await timescale_client.get_sensor_data(
            sensor_id, reading_type, start_time, end_time
        )
    
    async def get_real_time_dashboard_data(self) -> Dict[str, Any]:
        """Obtener datos para dashboard en tiempo real"""
        try:
            # Datos en tiempo real de todos los sensores
            real_time_data = await timescale_client.get_real_time_data(
                last_minutes=10
            )
            
            # Estadísticas generales
            stats = await timescale_client.get_sensor_statistics(
                time_window_hours=24
            )
            
            # Lista de sensores
            sensors_list = await self.get_sensors_list()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "total_sensors": len(self.sensors),
                "active_sensors": len([s for s in self.sensors.values() if s.active]),
                "simulation_running": self.simulation_running,
                "real_time_data": real_time_data,
                "statistics": stats,
                "sensors": sensors_list
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de dashboard: {e}")
            return {}

# Instancia global del servicio
sensor_service = SensorService()