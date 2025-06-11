"""Router para endpoints de series temporales y datos IoT"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.sensor_service import sensor_service
from database.timescale_client import timescale_client
from utils.twilio_utils import twilio_notifier
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class SensorReading(BaseModel):
    """Modelo para lectura de sensor"""
    sensor_id: str
    reading_type: str
    value: float
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class AlertRequest(BaseModel):
    """Modelo para solicitud de alerta"""
    phone_number: str
    message: str

@router.get("/sensors")
async def get_sensors(active_only: bool = Query(True)):
    """Obtener lista de sensores registrados"""
    try:
        sensors = await sensor_service.get_sensors_list()
        
        if active_only:
            sensors = [s for s in sensors if s.get("active", True)]
        
        return {
            "total": len(sensors),
            "sensors": sensors
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo sensores: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensors/{sensor_id}/data")
async def get_sensor_data(
    sensor_id: str,
    reading_type: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168)
):
    """Obtener datos históricos de un sensor"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        data = await timescale_client.get_sensor_data(
            sensor_id, reading_type, start_time, end_time
        )
        
        return {
            "sensor_id": sensor_id,
            "reading_type": reading_type,
            "time_range_hours": hours,
            "total_readings": len(data),
            "data": data
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo datos del sensor: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensors/real-time")
async def get_real_time_data(
    sensor_ids: Optional[List[str]] = Query(None),
    sensor_types: Optional[List[str]] = Query(None),
    last_minutes: int = Query(10, ge=1, le=60)
):
    """Obtener datos en tiempo real de sensores"""
    try:
        real_time_data = await timescale_client.get_real_time_data(
            sensor_ids, sensor_types, last_minutes
        )
        
        return real_time_data
        
    except Exception as e:
        logger.error(f"Error obteniendo datos en tiempo real: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensors/{sensor_id}/anomalies")
async def detect_anomalies(
    sensor_id: str,
    reading_type: str,
    threshold_multiplier: float = Query(2.0, ge=1.0, le=5.0),
    time_window_hours: int = Query(24, ge=6, le=168)
):
    """Detectar anomalías en datos de sensor"""
    try:
        anomalies = await timescale_client.detect_anomalies(
            sensor_id, reading_type, threshold_multiplier, time_window_hours
        )
        
        return {
            "sensor_id": sensor_id,
            "reading_type": reading_type,
            "threshold_multiplier": threshold_multiplier,
            "time_window_hours": time_window_hours,
            "anomalies_found": len(anomalies),
            "anomalies": anomalies
        }
        
    except Exception as e:
        logger.error(f"Error detectando anomalías: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/aggregates/hourly")
async def get_hourly_aggregates(
    sensor_id: Optional[str] = None,
    reading_type: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720)
):
    """Obtener datos agregados por hora"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        aggregates = await timescale_client.get_hourly_aggregates(
            sensor_id, reading_type, start_time, end_time
        )
        
        return {
            "sensor_id": sensor_id,
            "reading_type": reading_type,
            "time_range_hours": hours,
            "aggregates_count": len(aggregates),
            "aggregates": aggregates
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo agregados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_sensor_statistics(
    sensor_id: Optional[str] = None,
    time_window_hours: int = Query(24, ge=1, le=720)
):
    """Obtener estadísticas de sensores"""
    try:
        stats = await timescale_client.get_sensor_statistics(
            sensor_id, time_window_hours
        )
        
        return {
            "time_window_hours": time_window_hours,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sensors/{sensor_id}/readings")
async def add_sensor_reading(sensor_id: str, reading: SensorReading):
    """Añadir nueva lectura de sensor"""
    try:
        success = await sensor_service.record_reading(
            sensor_id,
            reading.reading_type,
            reading.value,
            reading.timestamp,
            reading.metadata
        )
        
        if success:
            return {"message": "Lectura registrada correctamente"}
        else:
            raise HTTPException(status_code=400, detail="Error registrando lectura")
            
    except Exception as e:
        logger.error(f"Error añadiendo lectura: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulation/start")
async def start_simulation():
    """Iniciar simulación de datos de sensores"""
    try:
        await sensor_service.start_simulation()
        return {"message": "Simulación iniciada", "status": "running"}
        
    except Exception as e:
        logger.error(f"Error iniciando simulación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulation/stop")
async def stop_simulation():
    """Detener simulación de datos de sensores"""
    try:
        await sensor_service.stop_simulation()
        return {"message": "Simulación detenida", "status": "stopped"}
        
    except Exception as e:
        logger.error(f"Error deteniendo simulación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/simulation/status")
async def get_simulation_status():
    """Obtener estado de la simulación"""
    try:
        return {
            "running": sensor_service.simulation_running,
            "total_sensors": len(sensor_service.sensors),
            "interval_seconds": settings.sensors.simulation_interval
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de simulación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/sms")
async def send_sms_alert(alert: AlertRequest, background_tasks: BackgroundTasks):
    """Enviar alerta SMS"""
    try:
        if not settings.twilio.is_configured:
            raise HTTPException(
                status_code=503, 
                detail="Servicio SMS no configurado"
            )
        
        # Enviar SMS en background para no bloquear la respuesta
        background_tasks.add_task(
            twilio_notifier.send_sms,
            alert.phone_number,
            alert.message
        )
        
        return {"message": "SMS enviado"}
        
    except Exception as e:
        logger.error(f"Error enviando SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Obtener resumen para dashboard"""
    try:
        dashboard_data = await sensor_service.get_real_time_dashboard_data()
        
        return {
            "timestamp": dashboard_data.get("timestamp"),
            "total_sensors": dashboard_data.get("total_sensors", 0),
            "active_sensors": dashboard_data.get("active_sensors", 0),
            "simulation_running": dashboard_data.get("simulation_running", False),
            "recent_data": dashboard_data.get("real_time_data", {}),
            "statistics": dashboard_data.get("statistics", {})
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen de dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))