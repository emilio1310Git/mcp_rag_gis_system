"""
Router API para funcionalidades TimescaleDB
Endpoints para sensores, observaciones, alertas y refugios
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ...services.timescale_service import TimescaleService
from ...services.twilio_service import TwilioService
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
timescale_service = TimescaleService()
twilio_service = TwilioService()

# Modelos Pydantic para requests/responses

class ObservacionCreate(BaseModel):
    """Modelo para crear nueva observación"""
    sensor_id: int
    valor: float
    unidad: str = "°C"
    calidad_dato: str = "buena"
    fecha_observacion: Optional[datetime] = None
    metadatos: Optional[Dict[str, Any]] = {}

class ObservacionResponse(BaseModel):
    """Respuesta de observación"""
    id: int
    sensor_id: int
    sensor_nombre: str
    valor: float
    unidad: str
    fecha_observacion: datetime
    calidad_dato: str
    nivel_bateria: Optional[float]
    intensidad_senal: Optional[float]
    lat: Optional[float]
    lon: Optional[float]

class SensorResponse(BaseModel):
    """Respuesta de sensor"""
    id: int
    nombre: str
    tipo_sensor: str
    estado: str
    unidad_medida: str
    lat: float
    lon: float
    fabricante: Optional[str]
    modelo: Optional[str]
    observaciones_ultima_hora: int
    valor_promedio: Optional[float]
    ultima_observacion: Optional[datetime]
    bateria_promedio: Optional[float]

class AlertaResponse(BaseModel):
    """Respuesta de alerta"""
    id: str
    sensor_id: int
    sensor_nombre: str
    refugio_id: Optional[int]
    refugio_nombre: Optional[str]
    tipo_alerta: str
    severidad: str
    valor_actual: float
    umbral_configurado: Optional[float]
    fecha_deteccion: datetime
    mensaje_alerta: Optional[str]
    sms_enviado: bool
    email_enviado: bool
    sensor_lat: float
    sensor_lon: float
    refugio_lat: Optional[float]
    refugio_lon: Optional[float]

class RefugioResponse(BaseModel):
    """Respuesta de refugio"""
    id: int
    nombre: str
    tipo_refugio: str
    estado_operativo: str
    capacidad_maxima: int
    capacidad_actual: int
    porcentaje_ocupacion: float
    tiene_aire_acondicionado: bool
    tiene_calefaccion: bool
    tiene_servicio_medico: bool
    telefono: Optional[str]
    responsable: Optional[str]
    lat: float
    lon: float
    distancia_km: float

class AgregadoHorario(BaseModel):
    """Agregado horario de temperatura"""
    hora: datetime
    sensor_id: int
    temp_media: float
    temp_min: float
    temp_max: float
    num_observaciones: int
    desviacion_estandar: Optional[float]

class EstadisticasTiempoReal(BaseModel):
    """Estadísticas del sistema en tiempo real"""
    timestamp: datetime
    sensores: Dict[str, Any]
    alertas: Dict[str, Any]
    refugios: Dict[str, Any]
    observaciones: Dict[str, Any]
    sistema: Dict[str, Any]

# Endpoints para sensores

@router.get("/sensores", response_model=List[SensorResponse])
async def get_sensores(
    tipo_sensor: Optional[str] = Query(None, description="Filtrar por tipo de sensor")
):
    """Obtener lista de sensores activos"""
    try:
        sensores = await timescale_service.get_sensores_activos(tipo_sensor)
        
        return [SensorResponse(**sensor) for sensor in sensores]
        
    except Exception as e:
        logger.error(f"Error obteniendo sensores: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/sensores/{sensor_id}/observaciones", response_model=List[ObservacionResponse])
async def get_observaciones_sensor(
    sensor_id: int,
    horas_atras: int = Query(24, description="Horas hacia atrás", ge=1, le=168),
    limite: int = Query(1000, description="Límite de resultados", ge=1, le=10000)
):
    """Obtener observaciones de un sensor específico"""
    try:
        observaciones = await timescale_service.get_observaciones_recientes(
            sensor_id=sensor_id,
            horas_atras=horas_atras,
            limite=limite
        )
        
        return [ObservacionResponse(**obs) for obs in observaciones]
        
    except Exception as e:
        logger.error(f"Error obteniendo observaciones del sensor {sensor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/sensores/{sensor_id}/agregados", response_model=List[AgregadoHorario])
async def get_agregados_sensor(
    sensor_id: int,
    horas_atras: int = Query(48, description="Horas hacia atrás", ge=1, le=720)
):
    """Obtener agregados horarios de un sensor"""
    try:
        agregados = await timescale_service.get_agregados_horarios(
            sensor_id=sensor_id,
            horas_atras=horas_atras
        )
        
        return [AgregadoHorario(**agg) for agg in agregados]
        
    except Exception as e:
        logger.error(f"Error obteniendo agregados del sensor {sensor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para observaciones

@router.post("/observaciones", response_model=dict)
async def crear_observacion(observacion: ObservacionCreate):
    """Crear nueva observación de sensor"""
    try:
        success = await timescale_service.insertar_observacion(
            sensor_id=observacion.sensor_id,
            valor=observacion.valor,
            unidad=observacion.unidad,
            fecha_observacion=observacion.fecha_observacion,
            calidad_dato=observacion.calidad_dato,
            metadatos=observacion.metadatos
        )
        
        if success:
            return {
                "message": "Observación creada exitosamente",
                "sensor_id": observacion.sensor_id,
                "valor": observacion.valor,
                "timestamp": observacion.fecha_observacion or datetime.utcnow()
            }
        else:
            raise HTTPException(status_code=400, detail="No se pudo crear la observación")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando observación: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/observaciones", response_model=List[ObservacionResponse])
async def get_observaciones_recientes(
    horas_atras: int = Query(24, description="Horas hacia atrás", ge=1, le=168),
    limite: int = Query(100, description="Límite de resultados", ge=1, le=1000)
):
    """Obtener observaciones recientes de todos los sensores"""
    try:
        observaciones = await timescale_service.get_observaciones_recientes(
            horas_atras=horas_atras,
            limite=limite
        )
        
        return [ObservacionResponse(**obs) for obs in observaciones]
        
    except Exception as e:
        logger.error(f"Error obteniendo observaciones recientes: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para alertas

@router.get("/alertas", response_model=List[AlertaResponse])
async def get_alertas_activas(
    severidad: Optional[str] = Query(None, description="Filtrar por severidad"),
    tipo_alerta: Optional[str] = Query(None, description="Filtrar por tipo de alerta"),
    limite: int = Query(100, description="Límite de resultados", ge=1, le=500)
):
    """Obtener alertas activas"""
    try:
        alertas = await timescale_service.get_alertas_activas(
            severidad=severidad,
            tipo_alerta=tipo_alerta,
            limite=limite
        )
        
        return [AlertaResponse(**alerta) for alerta in alertas]
        
    except Exception as e:
        logger.error(f"Error obteniendo alertas activas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.put("/alertas/{alerta_id}/resolver")
async def resolver_alerta(
    alerta_id: str,
    usuario: str = Query("api_user", description="Usuario que resuelve la alerta")
):
    """Resolver una alerta activa"""
    try:
        success = await timescale_service.resolver_alerta(alerta_id, usuario)
        
        if success:
            return {
                "message": "Alerta resuelta exitosamente",
                "alerta_id": alerta_id,
                "resuelto_por": usuario,
                "timestamp": datetime.utcnow()
            }
        else:
            raise HTTPException(status_code=404, detail="Alerta no encontrada o ya resuelta")
            
    except Exception as e:
        logger.error(f"Error resolviendo alerta {alerta_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/alertas/{alerta_id}/enviar-sms")
async def enviar_sms_alerta(
    alerta_id: str,
    numero_telefono: str = Query(..., description="Número de teléfono destino"),
    background_tasks: BackgroundTasks = None
):
    """Enviar SMS para una alerta específica"""
    try:
        # Obtener detalles de la alerta
        alertas = await timescale_service.get_alertas_activas()
        alerta = next((a for a in alertas if a['id'] == alerta_id), None)
        
        if not alerta:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
        # Crear mensaje SMS
        mensaje = f"""
🚨 ALERTA {alerta['severidad'].upper()}
Sensor: {alerta['sensor_nombre']}
Tipo: {alerta['tipo_alerta']}
Valor: {alerta['valor_actual']}°C
Ubicación: {alerta['sensor_lat']:.4f}, {alerta['sensor_lon']:.4f}
Hora: {alerta['fecha_deteccion'].strftime('%d/%m/%Y %H:%M')}
        """.strip()
        
        # Enviar SMS en background si es posible
        if background_tasks:
            background_tasks.add_task(
                twilio_service.send_sms,
                numero_telefono,
                mensaje
            )
            
            return {
                "message": "SMS programado para envío",
                "alerta_id": alerta_id,
                "numero_destino": numero_telefono
            }
        else:
            # Enviar SMS directamente
            sms_id = await twilio_service.send_sms(numero_telefono, mensaje)
            
            return {
                "message": "SMS enviado exitosamente",
                "alerta_id": alerta_id,
                "sms_id": sms_id,
                "numero_destino": numero_telefono
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enviando SMS para alerta {alerta_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para refugios

@router.get("/refugios/cercanos", response_model=List[RefugioResponse])
async def get_refugios_cercanos(
    lat: float = Query(..., description="Latitud", ge=-90, le=90),
    lon: float = Query(..., description="Longitud", ge=-180, le=180),
    radio_km: float = Query(10.0, description="Radio en kilómetros", ge=0.1, le=100),
    incluir_llenos: bool = Query(False, description="Incluir refugios llenos")
):
    """Obtener refugios cercanos a una ubicación"""
    try:
        refugios = await timescale_service.get_refugios_cercanos(
            lat=lat,
            lon=lon,
            radio_km=radio_km,
            incluir_llenos=incluir_llenos
        )
        
        return [RefugioResponse(**refugio) for refugio in refugios]
        
    except Exception as e:
        logger.error(f"Error obteniendo refugios cercanos: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.put("/refugios/{refugio_id}/capacidad")
async def actualizar_capacidad_refugio(
    refugio_id: int,
    nueva_capacidad: int = Query(..., description="Nueva capacidad actual", ge=0),
    usuario: str = Query("api_user", description="Usuario que actualiza")
):
    """Actualizar capacidad actual de un refugio"""
    try:
        success = await timescale_service.actualizar_capacidad_refugio(
            refugio_id=refugio_id,
            nueva_capacidad=nueva_capacidad,
            usuario=usuario
        )
        
        if success:
            return {
                "message": "Capacidad actualizada exitosamente",
                "refugio_id": refugio_id,
                "nueva_capacidad": nueva_capacidad,
                "actualizado_por": usuario,
                "timestamp": datetime.utcnow()
            }
        else:
            raise HTTPException(status_code=400, detail="No se pudo actualizar la capacidad")
            
    except Exception as e:
        logger.error(f"Error actualizando capacidad refugio {refugio_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para rutas

@router.get("/rutas/refugio/{sensor_id}/{refugio_id}")
async def calcular_ruta_refugio(
    sensor_id: int,
    refugio_id: int
):
    """Calcular ruta óptima desde sensor hasta refugio"""
    try:
        ruta = await timescale_service.calcular_ruta_refugio(
            sensor_id=sensor_id,
            refugio_id=refugio_id
        )
        
        if not ruta:
            raise HTTPException(
                status_code=404, 
                detail="No se pudo calcular ruta entre sensor y refugio"
            )
        
        # Calcular distancia total y tiempo estimado
        distancia_total = sum(segmento['cost'] for segmento in ruta)
        tiempo_estimado = distancia_total  # En minutos
        
        # Crear GeoJSON de la ruta
        features = []
        for segmento in ruta:
            import json
            geom = json.loads(segmento['geojson'])
            
            feature = {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "step_seq": segmento['step_seq'],
                    "edge_id": segmento['edge_id'],
                    "cost": segmento['cost']
                }
            }
            features.append(feature)
        
        ruta_geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return {
            "sensor_id": sensor_id,
            "refugio_id": refugio_id,
            "distancia_total_minutos": round(distancia_total, 2),
            "tiempo_estimado_minutos": round(tiempo_estimado, 2),
            "num_segmentos": len(ruta),
            "ruta_geojson": ruta_geojson
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculando ruta: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para mapas y reportes

@router.post("/mapas/alertas")
async def crear_mapa_alertas(
    centro_lat: float = Query(40.4168, description="Latitud del centro", ge=-90, le=90),
    centro_lon: float = Query(-3.7038, description="Longitud del centro", ge=-180, le=180),
    zoom: int = Query(10, description="Nivel de zoom", ge=1, le=18),
    incluir_rutas: bool = Query(True, description="Incluir rutas de evacuación")
):
    """Crear mapa interactivo con alertas, sensores y refugios"""
    try:
        map_filename = await timescale_service.crear_mapa_alertas(
            centro_lat=centro_lat,
            centro_lon=centro_lon,
            zoom=zoom,
            incluir_rutas=incluir_rutas
        )
        
        map_url = f"http://{settings.api.host}:{settings.api.port}/map/{map_filename}"
        
        return {
            "map_filename": map_filename,
            "map_url": map_url,
            "centro_lat": centro_lat,
            "centro_lon": centro_lon,
            "incluye_rutas": incluir_rutas,
            "fecha_creacion": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error creando mapa de alertas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/informes/alertas")
async def generar_informe_alertas(
    zona_lat: float = Query(..., description="Latitud del centro de la zona", ge=-90, le=90),
    zona_lon: float = Query(..., description="Longitud del centro de la zona", ge=-180, le=180),
    radio_km: float = Query(10.0, description="Radio de la zona en km", ge=0.1, le=100),
    periodo_horas: int = Query(24, description="Período de análisis en horas", ge=1, le=720)
):
    """Generar informe completo de alertas para una zona"""
    try:
        informe = await timescale_service.generar_informe_alertas(
            zona_lat=zona_lat,
            zona_lon=zona_lon,
            radio_km=radio_km,
            periodo_horas=periodo_horas
        )
        
        return informe
        
    except Exception as e:
        logger.error(f"Error generando informe de alertas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/estadisticas/tiempo-real", response_model=EstadisticasTiempoReal)
async def get_estadisticas_tiempo_real():
    """Obtener estadísticas del sistema en tiempo real"""
    try:
        estadisticas = await timescale_service.get_estadisticas_tiempo_real()
        
        return EstadisticasTiempoReal(**estadisticas)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas tiempo real: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoints para dashboards y monitoreo

@router.get("/dashboard/resumen")
async def get_dashboard_resumen():
    """Obtener resumen para dashboard principal"""
    try:
        # Obtener estadísticas tiempo real
        stats = await timescale_service.get_estadisticas_tiempo_real()
        
        # Obtener alertas más críticas
        alertas_criticas = await timescale_service.get_alertas_activas(
            severidad="critica",
            limite=5
        )
        
        # Obtener sensores con problemas
        sensores = await timescale_service.get_sensores_activos()
        sensores_sin_datos = [
            s for s in sensores 
            if s['observaciones_ultima_hora'] == 0 or s['bateria_promedio'] < 20
        ]
        
        # Calcular métricas clave
        total_sensores = len(sensores)
        sensores_activos = len([s for s in sensores if s['observaciones_ultima_hora'] > 0])
        porcentaje_disponibilidad = (sensores_activos / total_sensores * 100) if total_sensores > 0 else 0
        
        return {
            "timestamp": datetime.utcnow(),
            "resumen_general": {
                "estado_sistema": stats['sistema']['estado_general'],
                "total_sensores": total_sensores,
                "sensores_activos": sensores_activos,
                "disponibilidad_porcentaje": round(porcentaje_disponibilidad, 1),
                "alertas_criticas": len(alertas_criticas),
                "temperatura_promedio": stats['observaciones'].get('temperatura_promedio'),
                "observaciones_ultima_hora": stats['observaciones'].get('observaciones_ultima_hora', 0)
            },
            "alertas_criticas": alertas_criticas[:5],  # Top 5
            "sensores_problemas": sensores_sin_datos[:10],  # Top 10
            "metricas_rendimiento": {
                "bateria_promedio_sistema": stats['observaciones'].get('bateria_promedio'),
                "temperatura_minima": stats['observaciones'].get('temperatura_minima'),
                "temperatura_maxima": stats['observaciones'].get('temperatura_maxima'),
                "refugios_disponibles": stats['refugios'].get('refugios_disponibles', 0),
                "capacidad_refugios_disponible": stats['refugios'].get('capacidad_total', 0) - stats['refugios'].get('ocupacion_actual', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/healthcheck")
async def healthcheck():
    """Verificar salud del sistema TimescaleDB"""
    try:
        # Verificar conexión a base de datos
        test_query = "SELECT 1 as test"
        result = await timescale_service.postgres_client.execute_query(test_query)
        db_ok = result and result[0]['test'] == 1
        
        # Verificar TimescaleDB
        timescale_query = "SELECT extname FROM pg_extension WHERE extname = 'timescaledb'"
        timescale_result = await timescale_service.postgres_client.execute_query(timescale_query)
        timescale_ok = bool(timescale_result)
        
        # Verificar datos recientes
        recent_query = """
        SELECT COUNT(*) as count 
        FROM observaciones 
        WHERE fecha_observacion >= NOW() - INTERVAL '1 hour'
        """
        recent_result = await timescale_service.postgres_client.execute_query(recent_query)
        recent_data = recent_result[0]['count'] if recent_result else 0
        
        # Verificar continuous aggregates
        agg_query = """
        SELECT COUNT(*) as count 
        FROM temp_horaria 
        WHERE hora >= NOW() - INTERVAL '24 hours'
        """
        agg_result = await timescale_service.postgres_client.execute_query(agg_query)
        aggregates_ok = agg_result and agg_result[0]['count'] > 0
        
        status = "healthy" if all([db_ok, timescale_ok, aggregates_ok]) else "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.utcnow(),
            "checks": {
                "database_connection": db_ok,
                "timescaledb_extension": timescale_ok,
                "recent_data_count": recent_data,
                "continuous_aggregates": aggregates_ok
            },
            "version": "2.0",
            "uptime_hours": "N/A"  # Se puede calcular si se guarda el tiempo de inicio
        }
        
    except Exception as e:
        logger.error(f"Error en healthcheck: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow(),
            "error": str(e)
        }

# Endpoints para testing y desarrollo

@router.post("/test/generar-observaciones")
async def generar_observaciones_test(
    sensor_id: int = Query(..., description="ID del sensor"),
    num_observaciones: int = Query(10, description="Número de observaciones", ge=1, le=100),
    intervalo_minutos: int = Query(60, description="Intervalo entre observaciones", ge=1, le=1440),
    temp_base: float = Query(20.0, description="Temperatura base", ge=-50, le=60),
    variacion: float = Query(5.0, description="Variación máxima", ge=0, le=20)
):
    """Generar observaciones de prueba para un sensor (solo para desarrollo)"""
    try:
        import random
        
        observaciones_creadas = []
        
        for i in range(num_observaciones):
            # Calcular tiempo hacia atrás
            tiempo_observacion = datetime.utcnow() - timedelta(
                minutes=i * intervalo_minutos
            )
            
            # Generar valor aleatorio
            valor = temp_base + random.uniform(-variacion, variacion)
            
            # Crear observación
            success = await timescale_service.insertar_observacion(
                sensor_id=sensor_id,
                valor=round(valor, 2),
                unidad="°C",
                fecha_observacion=tiempo_observacion,
                calidad_dato="buena",
                metadatos={
                    "nivel_bateria": random.uniform(70, 100),
                    "intensidad_senal": random.uniform(-80, -40)
                }
            )
            
            if success:
                observaciones_creadas.append({
                    "timestamp": tiempo_observacion,
                    "valor": round(valor, 2)
                })
        
        return {
            "message": f"Generadas {len(observaciones_creadas)} observaciones de prueba",
            "sensor_id": sensor_id,
            "observaciones_creadas": len(observaciones_creadas),
            "rango_temporal": {
                "desde": observaciones_creadas[-1]["timestamp"] if observaciones_creadas else None,
                "hasta": observaciones_creadas[0]["timestamp"] if observaciones_creadas else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error generando observaciones de prueba: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")