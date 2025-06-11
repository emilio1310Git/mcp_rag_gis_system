"""Servidor MCP para TimescaleDB e IoT sensors"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta

# Configurar path para importaciones
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Importaciones del proyecto (ahora absolutas)
from services.sensor_service import sensor_service
from database.timescale_client import timescale_client
from config import settings

# Importaciones MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Crear servidor MCP
app = Server("timescale-server-v1")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Listar herramientas TimescaleDB disponibles"""
    return [
        Tool(
            name="initialize_timescale",
            description="Inicializar TimescaleDB y servicios de sensores IoT",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_sensors_list",
            description="Obtener lista de sensores IoT registrados",
            inputSchema={
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Solo sensores activos",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="detect_anomalies",
            description="Detectar anomalías en datos de sensores usando análisis estadístico",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "string",
                        "description": "ID del sensor a analizar"
                    },
                    "reading_type": {
                        "type": "string",
                        "enum": settings.sensors.supported_types,
                        "description": "Tipo de lectura a analizar"
                    },
                    "threshold_multiplier": {
                        "type": "number",
                        "description": "Multiplicador de desviación estándar para detección",
                        "default": 2.0,
                        "minimum": 1.0,
                        "maximum": 5.0
                    },
                    "time_window_hours": {
                        "type": "integer",
                        "description": "Ventana de tiempo para análisis",
                        "default": 24,
                        "minimum": 6,
                        "maximum": 168
                    }
                },
                "required": ["sensor_id", "reading_type"]
            }
        ),
        Tool(
            name="get_sensor_statistics",
            description="Obtener estadísticas detalladas de sensores",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "string",
                        "description": "ID específico del sensor (opcional)"
                    },
                    "time_window_hours": {
                        "type": "integer",
                        "description": "Ventana de tiempo para estadísticas",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 720
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="simulate_sensor_data",
            description="Controlar simulación de datos de sensores",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status"],
                        "description": "Acción a realizar con la simulación"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="create_custom_query",
            description="Ejecutar consulta personalizada en TimescaleDB",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["correlation", "trends", "peaks", "averages"],
                        "description": "Tipo de análisis a realizar"
                    },
                    "sensor_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de IDs de sensores"
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "description": "Rango de tiempo en horas",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 720
                    }
                },
                "required": ["query_type"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Ejecutar herramientas TimescaleDB"""
    
    try:
        if name == "initialize_timescale":
            await sensor_service.initialize()
            return [TextContent(
                type="text",
                text="✅ TimescaleDB y servicios de sensores IoT inicializados correctamente"
            )]
        
        elif name == "get_sensors_list":
            active_only = arguments.get("active_only", True)
            sensors = await sensor_service.get_sensors_list()
            
            if active_only:
                sensors = [s for s in sensors if s.get("active", True)]
            
            result = f"📱 **Sensores IoT registrados:** {len(sensors)}\n\n"
            
            if sensors:
                # Agrupar por tipo
                by_type = {}
                for sensor in sensors:
                    sensor_type = sensor["sensor_type"]
                    if sensor_type not in by_type:
                        by_type[sensor_type] = []
                    by_type[sensor_type].append(sensor)
                
                result += "📊 **Por tipo de sensor:**\n"
                for sensor_type, type_sensors in by_type.items():
                    result += f"• **{sensor_type.title()}:** {len(type_sensors)} sensores\n"
                
                result += "\n🔍 **Detalles de sensores:**\n"
                for sensor in sensors[:10]:  # Mostrar solo los primeros 10
                    result += f"• **{sensor['sensor_id']}** ({sensor['sensor_type']})\n"
                    result += f"  📍 {sensor['name']}\n"
                    result += f"  🌍 Lat: {sensor['location']['lat']:.6f}, Lon: {sensor['location']['lon']:.6f}\n"
                    if sensor.get('equipment_id'):
                        result += f"  🏢 Equipamiento: {sensor['equipment_id']}\n"
                    result += "\n"
                
                if len(sensors) > 10:
                    result += f"... y {len(sensors) - 10} sensores más\n"
            else:
                result += "⚠️ No hay sensores registrados"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_real_time_data":
            sensor_ids = arguments.get("sensor_ids")
            sensor_types = arguments.get("sensor_types")
            last_minutes = arguments.get("last_minutes", 10)
            
            real_time_data = await timescale_client.get_real_time_data(
                sensor_ids, sensor_types, last_minutes
            )
            
            result = f"⏰ **Datos en tiempo real** (últimos {last_minutes} minutos)\n"
            result += f"🕐 Timestamp: {real_time_data.get('timestamp', 'N/A')}\n\n"
            
            sensors_data = real_time_data.get('sensors', {})
            
            if sensors_data:
                result += f"📊 **{len(sensors_data)} sensores con datos:**\n\n"
                
                for sensor_id, readings in sensors_data.items():
                    result += f"🔹 **{sensor_id}**\n"
                    for reading_type, data in readings.items():
                        value = data['value']
                        timestamp = data['timestamp']
                        result += f"  • {reading_type}: {value} (⏰ {timestamp[-8:-3]})\n"
                    result += "\n"
            else:
                result += "⚠️ No hay datos recientes disponibles"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_sensor_history":
            sensor_id = arguments.get("sensor_id")
            reading_type = arguments.get("reading_type")
            hours = arguments.get("hours", 24)
            
            # Obtener datos históricos
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            history_data = await timescale_client.get_sensor_data(
                sensor_id, reading_type, start_time, end_time, limit=100
            )
            
            result = f"📈 **Histórico del sensor {sensor_id}**\n"
            if reading_type:
                result += f"🔍 Tipo: {reading_type}\n"
            result += f"⏰ Período: {hours} horas\n"
            result += f"📊 Registros: {len(history_data)}\n\n"
            
            if history_data:
                # Estadísticas básicas
                values = [float(d['value']) for d in history_data]
                avg_value = sum(values) / len(values)
                min_value = min(values)
                max_value = max(values)
                
                result += f"📊 **Estadísticas:**\n"
                result += f"• Promedio: {avg_value:.2f}\n"
                result += f"• Mínimo: {min_value:.2f}\n"
                result += f"• Máximo: {max_value:.2f}\n"
                result += f"• Variación: {max_value - min_value:.2f}\n\n"
                
                # Últimas 5 lecturas
                result += f"🕐 **Últimas lecturas:**\n"
                for reading in history_data[:5]:
                    timestamp = reading['timestamp'].strftime("%H:%M:%S")
                    result += f"• {reading['value']:.2f} ({timestamp})\n"
                
                if len(history_data) > 5:
                    result += f"... y {len(history_data) - 5} lecturas más\n"
            else:
                result += "⚠️ No hay datos históricos disponibles"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_hourly_aggregates":
            sensor_id = arguments.get("sensor_id")
            reading_type = arguments.get("reading_type")
            hours = arguments.get("hours", 24)
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            aggregates = await timescale_client.get_hourly_aggregates(
                sensor_id, reading_type, start_time, end_time
            )
            
            result = f"📊 **Agregados horarios**\n"
            if sensor_id:
                result += f"🔍 Sensor: {sensor_id}\n"
            if reading_type:
                result += f"📏 Tipo: {reading_type}\n"
            result += f"⏰ Período: {hours} horas\n"
            result += f"📈 Agregados: {len(aggregates)}\n\n"
            
            if aggregates:
                # Mostrar últimos 10 agregados
                result += f"📋 **Datos agregados por hora:**\n"
                for agg in aggregates[:10]:
                    hour = agg['hour'].strftime("%d/%m %H:00")
                    avg_val = agg['avg_value']
                    min_val = agg['min_value']
                    max_val = agg['max_value']
                    count = agg['readings_count']
                    
                    result += f"• **{hour}**: Avg {avg_val:.2f} (Min {min_val:.2f}, Max {max_val:.2f}) [{count} lecturas]\n"
                
                if len(aggregates) > 10:
                    result += f"... y {len(aggregates) - 10} horas más\n"
            else:
                result += "⚠️ No hay datos agregados disponibles"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "detect_anomalies":
            sensor_id = arguments.get("sensor_id")
            reading_type = arguments.get("reading_type")
            threshold_multiplier = arguments.get("threshold_multiplier", 2.0)
            time_window_hours = arguments.get("time_window_hours", 24)
            
            anomalies = await timescale_client.detect_anomalies(
                sensor_id, reading_type, threshold_multiplier, time_window_hours
            )
            
            result = f"🚨 **Detección de anomalías**\n"
            result += f"🔍 Sensor: {sensor_id} ({reading_type})\n"
            result += f"📊 Umbral: {threshold_multiplier}σ\n"
            result += f"⏰ Ventana: {time_window_hours}h\n"
            result += f"🎯 Anomalías encontradas: {len(anomalies)}\n\n"
            
            if anomalies:
                result += f"⚠️ **Anomalías detectadas:**\n"
                for anomaly in anomalies[:5]:  # Mostrar top 5
                    timestamp = anomaly['timestamp'].strftime("%d/%m %H:%M")
                    value = anomaly['value']
                    z_score = anomaly['z_score']
                    result += f"• **{timestamp}**: Valor {value:.2f} (Z-score: {z_score:.2f})\n"
                
                if len(anomalies) > 5:
                    result += f"... y {len(anomalies) - 5} anomalías más\n"
                
                result += f"\n💡 **Recomendación:**\n"
                if len(anomalies) > 10:
                    result += "Alto número de anomalías detectadas. Revisar calibración del sensor.\n"
                elif len(anomalies) > 5:
                    result += "Anomalías moderadas detectadas. Monitorización recomendada.\n"
                else:
                    result += "Pocas anomalías detectadas. Comportamiento normal del sensor.\n"
            else:
                result += "✅ No se detectaron anomalías en el período analizado"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_sensor_statistics":
            sensor_id = arguments.get("sensor_id")
            time_window_hours = arguments.get("time_window_hours", 24)
            
            stats = await timescale_client.get_sensor_statistics(
                sensor_id, time_window_hours
            )
            
            result = f"📊 **Estadísticas de sensores** ({time_window_hours}h)\n\n"
            
            if stats:
                if sensor_id:
                    # Estadísticas de un sensor específico
                    sensor_stats = stats.get(sensor_id, {})
                    if sensor_stats:
                        result += f"🔍 **Sensor: {sensor_id}**\n"
                        result += f"📈 Total lecturas: {sensor_stats['total_readings']:,}\n"
                        result += f"🕐 Primera lectura: {sensor_stats['first_reading']}\n"
                        result += f"🕐 Última lectura: {sensor_stats['last_reading']}\n\n"
                        
                        result += f"📋 **Por tipo de lectura:**\n"
                        for reading_type, type_stats in sensor_stats['readings'].items():
                            result += f"• **{reading_type}**:\n"
                            result += f"  - Lecturas: {type_stats['total_readings']:,}\n"
                            result += f"  - Promedio: {type_stats['avg_value']:.2f}\n"
                            result += f"  - Rango: {type_stats['min_value']:.2f} - {type_stats['max_value']:.2f}\n"
                            result += f"  - Desv. Estándar: {type_stats['std_value']:.2f}\n"
                    else:
                        result += f"⚠️ No hay estadísticas para el sensor {sensor_id}"
                else:
                    # Estadísticas globales
                    total_sensors = len(stats)
                    total_readings = sum(s['total_readings'] for s in stats.values())
                    
                    result += f"🌐 **Resumen global:**\n"
                    result += f"📱 Sensores activos: {total_sensors}\n"
                    result += f"📊 Total lecturas: {total_readings:,}\n\n"
                    
                    result += f"📋 **Top 5 sensores por actividad:**\n"
                    sorted_sensors = sorted(stats.items(), 
                                          key=lambda x: x[1]['total_readings'], 
                                          reverse=True)
                    
                    for sensor_id, sensor_stats in sorted_sensors[:5]:
                        result += f"• **{sensor_id}**: {sensor_stats['total_readings']:,} lecturas\n"
            else:
                result += "⚠️ No hay estadísticas disponibles"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "simulate_sensor_data":
            action = arguments.get("action")
            
            if action == "start":
                await sensor_service.start_simulation()
                result = "🟢 Simulación de sensores iniciada"
            elif action == "stop":
                await sensor_service.stop_simulation()
                result = "🔴 Simulación de sensores detenida"
            elif action == "status":
                status = "activa" if sensor_service.simulation_running else "inactiva"
                result = f"📊 Estado de simulación: {status}\n"
                result += f"📱 Sensores registrados: {len(sensor_service.sensors)}\n"
                result += f"⏰ Intervalo: {settings.sensors.simulation_interval}s"
            else:
                result = "❌ Acción no válida. Use: start, stop, status"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "create_custom_query":
            query_type = arguments.get("query_type")
            sensor_ids = arguments.get("sensor_ids", [])
            time_range_hours = arguments.get("time_range_hours", 24)
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)
            
            result = f"🔍 **Análisis personalizado: {query_type}**\n"
            result += f"⏰ Período: {time_range_hours}h\n"
            
            if query_type == "correlation":
                # Análisis de correlación entre sensores
                if len(sensor_ids) < 2:
                    result += "❌ Se necesitan al menos 2 sensores para análisis de correlación"
                else:
                    result += f"📊 Analizando correlación entre {len(sensor_ids)} sensores...\n"
                    result += "💡 Funcionalidad en desarrollo - próximamente disponible"
            
            elif query_type == "trends":
                # Análisis de tendencias
                result += f"📈 Análisis de tendencias para {len(sensor_ids)} sensores\n"
                result += "💡 Funcionalidad en desarrollo - próximamente disponible"
            
            elif query_type == "peaks":
                # Detección de picos
                result += f"⛰️ Detección de picos en {len(sensor_ids)} sensores\n"
                result += "💡 Funcionalidad en desarrollo - próximamente disponible"
            
            elif query_type == "averages":
                # Promedios móviles
                result += f"📊 Promedios móviles para {len(sensor_ids)} sensores\n"
                result += "💡 Funcionalidad en desarrollo - próximamente disponible"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"❌ Herramienta desconocida: {name}")]
    
    except Exception as e:
        logger.error(f"Error en herramienta TimescaleDB {name}: {e}")
        return [TextContent(type="text", text=f"❌ Error ejecutando {name}: {str(e)}")]

async def main():
    """Función principal del servidor TimescaleDB"""
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
        Tool(
            name="get_real_time_data",
            description="Obtener datos en tiempo real de sensores",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs específicos de sensores (opcional)"
                    },
                    "sensor_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": settings.sensors.supported_types
                        },
                        "description": "Tipos de sensores (opcional)"
                    },
                    "last_minutes": {
                        "type": "integer",
                        "description": "Minutos de datos recientes",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 60
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_sensor_history",
            description="Obtener histórico de datos de sensores",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "string",
                        "description": "ID del sensor"
                    },
                    "reading_type": {
                        "type": "string",
                        "enum": settings.sensors.supported_types,
                        "description": "Tipo de lectura del sensor"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Horas de histórico",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 168
                    }
                },
                "required": ["sensor_id"]
            }
        ),
        Tool(
            name="get_hourly_aggregates",
            description="Obtener datos agregados por hora usando continuous aggregates",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "string",
                        "description": "ID del sensor (opcional)"
                    },
                    "reading_type": {
                        "type": "string",
                        "enum": settings.sensors.supported_types,
                        "description": "Tipo de lectura (opcional)"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Horas de datos agregados",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 720
                    }