"""
Servidor MCP para TimescaleDB - Funcionalidades de sensores y alertas
Implementa la versión ampliada con sensores IoT, alertas y rutas de evacuación
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json

# Configurar path para importaciones
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Importaciones del proyecto
from services.timescale_service import TimescaleService
from services.twilio_service import TwilioService
from database import postgres_client
from config import settings

# Importaciones MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Inicializar servicios
timescale_service = TimescaleService()
twilio_service = TwilioService()

# Crear servidor MCP
app = Server("timescale-server-v2")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Listar herramientas TimescaleDB disponibles"""
    return [
        Tool(
            name="initialize_timescale",
            description="Inicializar conexión a TimescaleDB y servicios",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_sensores_activos",
            description="Obtener lista de sensores activos con estadísticas",
            inputSchema={
                "type": "object",
                "properties": {
                    "tipo_sensor": {
                        "type": "string",
                        "description": "Filtrar por tipo de sensor (opcional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="insertar_observacion",
            description="Insertar nueva observación de sensor",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID del sensor"
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor medido"
                    },
                    "unidad": {
                        "type": "string",
                        "description": "Unidad de medida",
                        "default": "°C"
                    },
                    "calidad_dato": {
                        "type": "string",
                        "description": "Calidad del dato",
                        "enum": ["buena", "regular", "mala", "dudosa"],
                        "default": "buena"
                    },
                    "metadatos": {
                        "type": "object",
                        "description": "Metadatos adicionales (batería, señal, etc.)"
                    }
                },
                "required": ["sensor_id", "valor"]
            }
        ),
        Tool(
            name="get_observaciones_recientes",
            description="Obtener observaciones recientes de sensores",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID del sensor específico (opcional)"
                    },
                    "horas_atras": {
                        "type": "integer",
                        "description": "Horas hacia atrás",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 168
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Límite de resultados",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_agregados_horarios",
            description="Obtener agregados horarios de temperatura",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID del sensor"
                    },
                    "horas_atras": {
                        "type": "integer",
                        "description": "Horas hacia atrás",
                        "default": 48,
                        "minimum": 1,
                        "maximum": 720
                    }
                },
                "required": ["sensor_id"]
            }
        ),
        Tool(
            name="get_alertas_activas",
            description="Obtener alertas activas del sistema",
            inputSchema={
                "type": "object",
                "properties": {
                    "severidad": {
                        "type": "string",
                        "description": "Filtrar por severidad",
                        "enum": ["critica", "alta", "media", "baja"]
                    },
                    "tipo_alerta": {
                        "type": "string",
                        "description": "Filtrar por tipo de alerta",
                        "enum": ["calor_extremo", "frio_extremo", "cambio_brusco"]
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Límite de resultados",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="resolver_alerta",
            description="Resolver una alerta activa",
            inputSchema={
                "type": "object",
                "properties": {
                    "alerta_id": {
                        "type": "string",
                        "description": "ID de la alerta a resolver"
                    },
                    "usuario": {
                        "type": "string",
                        "description": "Usuario que resuelve la alerta",
                        "default": "mcp_user"
                    }
                },
                "required": ["alerta_id"]
            }
        ),
        Tool(
            name="get_refugios_cercanos",
            description="Obtener refugios cercanos a una ubicación",
            inputSchema={
                "type": "object",
                "properties": {
                    "lat": {
                        "type": "number",
                        "description": "Latitud",
                        "minimum": -90,
                        "maximum": 90
                    },
                    "lon": {
                        "type": "number",
                        "description": "Longitud",
                        "minimum": -180,
                        "maximum": 180
                    },
                    "radio_km": {
                        "type": "number",
                        "description": "Radio de búsqueda en km",
                        "default": 10.0,
                        "minimum": 0.1,
                        "maximum": 100
                    },
                    "incluir_llenos": {
                        "type": "boolean",
                        "description": "Incluir refugios llenos",
                        "default": False
                    }
                },
                "required": ["lat", "lon"]
            }
        ),
        Tool(
            name="calcular_ruta_refugio",
            description="Calcular ruta óptima desde sensor hasta refugio",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID del sensor origen"
                    },
                    "refugio_id": {
                        "type": "integer",
                        "description": "ID del refugio destino"
                    }
                },
                "required": ["sensor_id", "refugio_id"]
            }
        ),
        Tool(
            name="enviar_sms_alerta",
            description="Enviar SMS de alerta a un número de teléfono",
            inputSchema={
                "type": "object",
                "properties": {
                    "alerta_id": {
                        "type": "string",
                        "description": "ID de la alerta"
                    },
                    "numero_telefono": {
                        "type": "string",
                        "description": "Número de teléfono destino (formato internacional)"
                    },
                    "incluir_ubicacion": {
                        "type": "boolean",
                        "description": "Incluir coordenadas en el SMS",
                        "default": True
                    }
                },
                "required": ["alerta_id", "numero_telefono"]
            }
        ),
        Tool(
            name="crear_mapa_alertas",
            description="Crear mapa interactivo con alertas y refugios",
            inputSchema={
                "type": "object",
                "properties": {
                    "centro_lat": {
                        "type": "number",
                        "description": "Latitud del centro del mapa",
                        "default": 40.4168
                    },
                    "centro_lon": {
                        "type": "number",
                        "description": "Longitud del centro del mapa",
                        "default": -3.7038
                    },
                    "zoom": {
                        "type": "integer",
                        "description": "Nivel de zoom",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 18
                    },
                    "incluir_rutas": {
                        "type": "boolean",
                        "description": "Incluir rutas de evacuación",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="generar_informe_alertas",
            description="Generar informe completo de alertas para una zona",
            inputSchema={
                "type": "object",
                "properties": {
                    "zona_lat": {
                        "type": "number",
                        "description": "Latitud del centro de la zona"
                    },
                    "zona_lon": {
                        "type": "number",
                        "description": "Longitud del centro de la zona"
                    },
                    "radio_km": {
                        "type": "number",
                        "description": "Radio de la zona en km",
                        "default": 10.0,
                        "minimum": 0.1,
                        "maximum": 100
                    },
                    "periodo_horas": {
                        "type": "integer",
                        "description": "Período de análisis en horas",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 720
                    }
                },
                "required": ["zona_lat", "zona_lon"]
            }
        ),
        Tool(
            name="get_estadisticas_tiempo_real",
            description="Obtener estadísticas del sistema en tiempo real",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="actualizar_capacidad_refugio",
            description="Actualizar capacidad actual de un refugio",
            inputSchema={
                "type": "object",
                "properties": {
                    "refugio_id": {
                        "type": "integer",
                        "description": "ID del refugio"
                    },
                    "nueva_capacidad": {
                        "type": "integer",
                        "description": "Nueva capacidad actual",
                        "minimum": 0
                    },
                    "usuario": {
                        "type": "string",
                        "description": "Usuario que actualiza",
                        "default": "mcp_user"
                    }
                },
                "required": ["refugio_id", "nueva_capacidad"]
            }
        ),
        Tool(
            name="generar_observaciones_test",
            description="Generar observaciones de prueba para un sensor",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID del sensor"
                    },
                    "num_observaciones": {
                        "type": "integer",
                        "description": "Número de observaciones",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "intervalo_minutos": {
                        "type": "integer",
                        "description": "Intervalo entre observaciones en minutos",
                        "default": 60,
                        "minimum": 1,
                        "maximum": 1440
                    },
                    "temp_base": {
                        "type": "number",
                        "description": "Temperatura base en °C",
                        "default": 20.0,
                        "minimum": -50,
                        "maximum": 60
                    },
                    "variacion": {
                        "type": "number",
                        "description": "Variación máxima en °C",
                        "default": 5.0,
                        "minimum": 0,
                        "maximum": 20
                    }
                },
                "required": ["sensor_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Ejecutar herramientas TimescaleDB"""
    
    try:
        if name == "initialize_timescale":
            await postgres_client.initialize()
            return [TextContent(
                type="text",
                text="✅ Servicios TimescaleDB inicializados correctamente"
            )]
        
        elif name == "get_sensores_activos":
            tipo_sensor = arguments.get("tipo_sensor")
            sensores = await timescale_service.get_sensores_activos(tipo_sensor)
            
            if not sensores:
                result = "📡 No se encontraron sensores activos"
            else:
                result = f"📡 **Sensores activos encontrados:** {len(sensores)}\n\n"
                
                for sensor in sensores:
                    result += f"**{sensor['nombre']}** (ID: {sensor['id']})\n"
                    result += f"• Tipo: {sensor['tipo_sensor']}\n"
                    result += f"• Estado: {sensor['estado']}\n"
                    result += f"• Ubicación: {sensor['lat']:.4f}, {sensor['lon']:.4f}\n"
                    result += f"• Última hora: {sensor['observaciones_ultima_hora']} observaciones\n"
                    
                    if sensor['valor_promedio']:
                        result += f"• Valor promedio: {sensor['valor_promedio']}°C\n"
                    if sensor['bateria_promedio']:
                        result += f"• Batería: {sensor['bateria_promedio']}%\n"
                    if sensor['ultima_observacion']:
                        result += f"• Última observación: {sensor['ultima_observacion']}\n"
                    
                    result += "\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "insertar_observacion":
            sensor_id = arguments.get("sensor_id")
            valor = arguments.get("valor")
            unidad = arguments.get("unidad", "°C")
            calidad_dato = arguments.get("calidad_dato", "buena")
            metadatos = arguments.get("metadatos", {})
            
            success = await timescale_service.insertar_observacion(
                sensor_id=sensor_id,
                valor=valor,
                unidad=unidad,
                calidad_dato=calidad_dato,
                metadatos=metadatos
            )
            
            if success:
                result = f"✅ **Observación insertada exitosamente**\n"
                result += f"• Sensor ID: {sensor_id}\n"
                result += f"• Valor: {valor} {unidad}\n"
                result += f"• Calidad: {calidad_dato}\n"
                result += f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                
                if metadatos:
                    result += f"• Metadatos: {metadatos}\n"
            else:
                result = f"❌ Error insertando observación para sensor {sensor_id}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_observaciones_recientes":
            sensor_id = arguments.get("sensor_id")
            horas_atras = arguments.get("horas_atras", 24)
            limite = arguments.get("limite", 100)
            
            observaciones = await timescale_service.get_observaciones_recientes(
                sensor_id=sensor_id,
                horas_atras=horas_atras,
                limite=limite
            )
            
            if not observaciones:
                result = f"📊 No se encontraron observaciones recientes"
            else:
                result = f"📊 **Observaciones recientes:** {len(observaciones)}\n"
                result += f"• Período: Últimas {horas_atras} horas\n"
                result += f"• Límite: {limite} registros\n\n"
                
                # Agrupar por sensor
                sensores_obs = {}
                for obs in observaciones:
                    sensor_name = obs['sensor_nombre']
                    if sensor_name not in sensores_obs:
                        sensores_obs[sensor_name] = []
                    sensores_obs[sensor_name].append(obs)
                
                for sensor_name, obs_list in sensores_obs.items():
                    result += f"**{sensor_name}:**\n"
                    
                    # Mostrar solo las primeras 10 observaciones por sensor
                    for obs in obs_list[:10]:
                        result += f"  • {obs['fecha_observacion']}: {obs['valor']}{obs['unidad']} ({obs['calidad_dato']})\n"
                    
                    if len(obs_list) > 10:
                        result += f"  ... y {len(obs_list) - 10} observaciones más\n"
                    
                    result += "\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_agregados_horarios":
            sensor_id = arguments.get("sensor_id")
            horas_atras = arguments.get("horas_atras", 48)
            
            agregados = await timescale_service.get_agregados_horarios(
                sensor_id=sensor_id,
                horas_atras=horas_atras
            )
            
            if not agregados:
                result = f"📈 No se encontraron agregados horarios para sensor {sensor_id}"
            else:
                result = f"📈 **Agregados horarios - Sensor {sensor_id}**\n"
                result += f"• Período: Últimas {horas_atras} horas\n"
                result += f"• Registros: {len(agregados)}\n\n"
                
                for agg in agregados[:24]:  # Mostrar últimas 24 horas
                    result += f"**{agg['hora']}:**\n"
                    result += f"  • Media: {agg['temp_media']}°C\n"
                    result += f"  • Mín: {agg['temp_min']}°C\n"
                    result += f"  • Máx: {agg['temp_max']}°C\n"
                    result += f"  • Observaciones: {agg['num_observaciones']}\n"
                    if agg['desviacion_estandar']:
                        result += f"  • Desv. estándar: {agg['desviacion_estandar']:.2f}°C\n"
                    result += "\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_alertas_activas":
            severidad = arguments.get("severidad")
            tipo_alerta = arguments.get("tipo_alerta")
            limite = arguments.get("limite", 50)
            
            alertas = await timescale_service.get_alertas_activas(
                severidad=severidad,
                tipo_alerta=tipo_alerta,
                limite=limite
            )
            
            if not alertas:
                result = "🔔 No hay alertas activas en el sistema"
            else:
                result = f"🚨 **Alertas activas:** {len(alertas)}\n\n"
                
                # Agrupar por severidad
                alertas_por_severidad = {"critica": [], "alta": [], "media": [], "baja": []}
                for alerta in alertas:
                    sev = alerta['severidad']
                    if sev in alertas_por_severidad:
                        alertas_por_severidad[sev].append(alerta)
                
                for severidad_nivel, alertas_sev in alertas_por_severidad.items():
                    if alertas_sev:
                        emoji = {"critica": "🔴", "alta": "🟠", "media": "🟡", "baja": "🔵"}
                        result += f"{emoji[severidad_nivel]} **Severidad {severidad_nivel.upper()} ({len(alertas_sev)}):**\n"
                        
                        for alerta in alertas_sev:
                            result += f"• **{alerta['sensor_nombre']}** - {alerta['tipo_alerta']}\n"
                            result += f"  Valor: {alerta['valor_actual']}°C (umbral: {alerta['umbral_configurado']}°C)\n"
                            result += f"  Ubicación: {alerta['sensor_lat']:.4f}, {alerta['sensor_lon']:.4f}\n"
                            result += f"  Fecha: {alerta['fecha_deteccion']}\n"
                            result += f"  ID: {alerta['id']}\n"
                            
                            if alerta['refugio_nombre']:
                                result += f"  Refugio asignado: {alerta['refugio_nombre']}\n"
                            
                            result += f"  SMS enviado: {'✅' if alerta['sms_enviado'] else '❌'}\n"
                            result += "\n"
                        
                        result += "\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "resolver_alerta":
            alerta_id = arguments.get("alerta_id")
            usuario = arguments.get("usuario", "mcp_user")
            
            success = await timescale_service.resolver_alerta(alerta_id, usuario)
            
            if success:
                result = f"✅ **Alerta resuelta exitosamente**\n"
                result += f"• ID: {alerta_id}\n"
                result += f"• Resuelto por: {usuario}\n"
                result += f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                result = f"❌ No se pudo resolver la alerta {alerta_id} (no encontrada o ya resuelta)"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_refugios_cercanos":
            lat = arguments.get("lat")
            lon = arguments.get("lon")
            radio_km = arguments.get("radio_km", 10.0)
            incluir_llenos = arguments.get("incluir_llenos", False)
            
            refugios = await timescale_service.get_refugios_cercanos(
                lat=lat,
                lon=lon,
                radio_km=radio_km,
                incluir_llenos=incluir_llenos
            )
            
            if not refugios:
                result = f"🏠 No se encontraron refugios en un radio de {radio_km} km"
            else:
                result = f"🏠 **Refugios cercanos:** {len(refugios)}\n"
                result += f"• Centro: {lat:.4f}, {lon:.4f}\n"
                result += f"• Radio: {radio_km} km\n"
                result += f"• Incluye llenos: {'Sí' if incluir_llenos else 'No'}\n\n"
                
                for refugio in refugios:
                    disponible = refugio['capacidad_maxima'] - refugio['capacidad_actual']
                    result += f"**{refugio['nombre']}** ({refugio['tipo_refugio']})\n"
                    result += f"• Estado: {refugio['estado_operativo']}\n"
                    result += f"• Distancia: {refugio['distancia_km']} km\n"
                    result += f"• Capacidad: {refugio['capacidad_actual']}/{refugio['capacidad_maxima']} ({disponible} disponibles)\n"
                    result += f"• Ocupación: {refugio['porcentaje_ocupacion']}%\n"
                    result += f"• Ubicación: {refugio['lat']:.4f}, {refugio['lon']:.4f}\n"
                    
                    servicios = []
                    if refugio['tiene_aire_acondicionado']:
                        servicios.append("AC")
                    if refugio['tiene_calefaccion']:
                        servicios.append("Calefacción")
                    if refugio['tiene_servicio_medico']:
                        servicios.append("Servicio médico")
                    
                    if servicios:
                        result += f"• Servicios: {', '.join(servicios)}\n"
                    
                    if refugio['telefono']:
                        result += f"• Teléfono: {refugio['telefono']}\n"
                    if refugio['responsable']:
                        result += f"• Responsable: {refugio['responsable']}\n"
                    
                    result += "\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "calcular_ruta_refugio":
            sensor_id = arguments.get("sensor_id")
            refugio_id = arguments.get("refugio_id")
            
            ruta = await timescale_service.calcular_ruta_refugio(sensor_id, refugio_id)
            
            if not ruta:
                result = f"❌ No se pudo calcular ruta entre sensor {sensor_id} y refugio {refugio_id}"
            else:
                distancia_total = sum(segmento['cost'] for segmento in ruta)
                
                result = f"🗺️ **Ruta de evacuación calculada**\n"
                result += f"• Sensor ID: {sensor_id}\n"
                result += f"• Refugio ID: {refugio_id}\n"
                result += f"• Distancia total: {distancia_total:.2f} minutos\n"
                result += f"• Número de segmentos: {len(ruta)}\n\n"
                
                result += "**Segmentos de la ruta:**\n"
                for i, segmento in enumerate(ruta[:10]):  # Mostrar primeros 10 segmentos
                    result += f"{i+1}. Tramo {segmento['edge_id']} - {segmento['cost']:.2f} min\n"
                
                if len(ruta) > 10:
                    result += f"... y {len(ruta) - 10} segmentos más\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "enviar_sms_alerta":
            alerta_id = arguments.get("alerta_id")
            numero_telefono = arguments.get("numero_telefono")
            incluir_ubicacion = arguments.get("incluir_ubicacion", True)
            
            # Obtener datos de la alerta
            alertas = await timescale_service.get_alertas_activas()
            alerta = next((a for a in alertas if a['id'] == alerta_id), None)
            
            if not alerta:
                result = f"❌ Alerta {alerta_id} no encontrada"
            else:
                # Enviar SMS
                sms_id = await twilio_service.send_alert_sms(
                    to_number=numero_telefono,
                    alert_data=alerta,
                    include_location=incluir_ubicacion
                )
                
                if sms_id:
                    result = f"📱 **SMS de alerta enviado exitosamente**\n"
                    result += f"• Alerta ID: {alerta_id}\n"
                    result += f"• Número destino: {numero_telefono}\n"
                    result += f"• SMS ID: {sms_id}\n"
                    result += f"• Ubicación incluida: {'Sí' if incluir_ubicacion else 'No'}\n"
                    result += f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                else:
                    result = f"❌ Error enviando SMS de alerta a {numero_telefono}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "crear_mapa_alertas":
            centro_lat = arguments.get("centro_lat", 40.4168)
            centro_lon = arguments.get("centro_lon", -3.7038)
            zoom = arguments.get("zoom", 10)
            incluir_rutas = arguments.get("incluir_rutas", True)
            
            map_filename = await timescale_service.crear_mapa_alertas(
                centro_lat=centro_lat,
                centro_lon=centro_lon,
                zoom=zoom,
                incluir_rutas=incluir_rutas
            )
            
            map_url = f"http://{settings.api.host}:{settings.api.port}/map/{map_filename}"
            
            result = f"🗺️ **Mapa de alertas creado**\n"
            result += f"• Centro: {centro_lat:.4f}, {centro_lon:.4f}\n"
            result += f"• Zoom: {zoom}\n"
            result += f"• Rutas incluidas: {'Sí' if incluir_rutas else 'No'}\n"
            result += f"• Archivo: {map_filename}\n"
            result += f"• URL: {map_url}\n"
            result += f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "generar_informe_alertas":
            zona_lat = arguments.get("zona_lat")
            zona_lon = arguments.get("zona_lon")
            radio_km = arguments.get("radio_km", 10.0)
            periodo_horas = arguments.get("periodo_horas", 24)
            
            informe = await timescale_service.generar_informe_alertas(
                zona_lat=zona_lat,
                zona_lon=zona_lon,
                radio_km=radio_km,
                periodo_horas=periodo_horas
            )
            
            result = f"📋 **Informe de Alertas**\n"
            result += f"• Zona: {zona_lat:.4f}, {zona_lon:.4f} (radio: {radio_km} km)\n"
            result += f"• Período: {periodo_horas} horas\n"
            result += f"• Nivel de riesgo: **{informe['nivel_riesgo']}**\n\n"
            
            resumen = informe['resumen_alertas']
            result += f"**Resumen de alertas:**\n"
            result += f"• Total: {resumen['total_alertas']}\n"
            result += f"• Críticas: {resumen['alertas_criticas']}\n"
            result += f"• Altas: {resumen['alertas_altas']}\n"
            result += f"• Medias: {resumen['alertas_medias']}\n\n"
            
            refugios_info = informe['refugios_zona']
            result += f"**Refugios en la zona:**\n"
            result += f"• Total: {refugios_info['total_refugios']}\n"
            result += f"• Disponibles: {refugios_info['refugios_disponibles']}\n"
            result += f"• Capacidad total: {refugios_info['capacidad_total']}\n"
            result += f"• Capacidad disponible: {refugios_info['capacidad_disponible']}\n"
            result += f"• Ocupación: {refugios_info['porcentaje_ocupacion']}%\n\n"
            
            if informe['recomendaciones']:
                result += f"**Recomendaciones:**\n"
                for rec in informe['recomendaciones']:
                    result += f"• {rec}\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_estadisticas_tiempo_real":
            stats = await timescale_service.get_estadisticas_tiempo_real()
            
            result = f"📊 **Estadísticas del Sistema en Tiempo Real**\n"
            result += f"• Timestamp: {stats['timestamp']}\n"
            result += f"• Estado general: **{stats['sistema']['estado_general']}**\n\n"
            
            sensores_stats = stats['sensores']
            result += f"**Sensores:**\n"
            result += f"• Total: {sensores_stats['total']}\n"
            result += f"• Activos última hora: {sensores_stats['activos_ultima_hora']}\n\n"
            
            alertas_stats = stats['alertas']
            result += f"**Alertas:**\n"
            result += f"• Total activas: {alertas_stats.get('total_alertas_activas', 0)}\n"
            result += f"• Críticas: {alertas_stats.get('alertas_criticas', 0)}\n"
            result += f"• Altas: {alertas_stats.get('alertas_altas', 0)}\n"
            result += f"• Medias: {alertas_stats.get('alertas_medias', 0)}\n"
            result += f"• Última hora: {alertas_stats.get('alertas_ultima_hora', 0)}\n\n"
            
            refugios_stats = stats['refugios']
            result += f"**Refugios:**\n"
            result += f"• Total: {refugios_stats.get('total_refugios', 0)}\n"
            result += f"• Disponibles: {refugios_stats.get('refugios_disponibles', 0)}\n"
            result += f"• Capacidad total: {refugios_stats.get('capacidad_total', 0):,}\n"
            result += f"• Ocupación actual: {refugios_stats.get('ocupacion_actual', 0):,}\n"
            result += f"• Ocupación promedio: {refugios_stats.get('ocupacion_promedio', 0)}%\n\n"
            
            obs_stats = stats['observaciones']
            result += f"**Observaciones (última hora):**\n"
            result += f"• Total: {obs_stats.get('observaciones_ultima_hora', 0):,}\n"
            result += f"• Sensores activos: {obs_stats.get('sensores_activos_ultima_hora', 0)}\n"
            result += f"• Temperatura promedio: {obs_stats.get('temperatura_promedio', 'N/A')}°C\n"
            result += f"• Temperatura mínima: {obs_stats.get('temperatura_minima', 'N/A')}°C\n"
            result += f"• Temperatura máxima: {obs_stats.get('temperatura_maxima', 'N/A')}°C\n"
            result += f"• Batería promedio: {obs_stats.get('bateria_promedio', 'N/A')}%\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "actualizar_capacidad_refugio":
            refugio_id = arguments.get("refugio_id")
            nueva_capacidad = arguments.get("nueva_capacidad")
            usuario = arguments.get("usuario", "mcp_user")
            
            success = await timescale_service.actualizar_capacidad_refugio(
                refugio_id=refugio_id,
                nueva_capacidad=nueva_capacidad,
                usuario=usuario
            )
            
            if success:
                result = f"✅ **Capacidad de refugio actualizada**\n"
                result += f"• Refugio ID: {refugio_id}\n"
                result += f"• Nueva capacidad: {nueva_capacidad}\n"
                result += f"• Actualizado por: {usuario}\n"
                result += f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                result = f"❌ Error actualizando capacidad del refugio {refugio_id}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "generar_observaciones_test":
            sensor_id = arguments.get("sensor_id")
            num_observaciones = arguments.get("num_observaciones", 10)
            intervalo_minutos = arguments.get("intervalo_minutos", 60)
            temp_base = arguments.get("temp_base", 20.0)
            variacion = arguments.get("variacion", 5.0)
            
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
            
            result = f"🧪 **Observaciones de prueba generadas**\n"
            result += f"• Sensor ID: {sensor_id}\n"
            result += f"• Observaciones creadas: {len(observaciones_creadas)}\n"
            result += f"• Intervalo: {intervalo_minutos} minutos\n"
            result += f"• Temperatura base: {temp_base}°C ± {variacion}°C\n"
            
            if observaciones_creadas:
                result += f"• Rango temporal:\n"
                result += f"  - Desde: {observaciones_creadas[-1]['timestamp']}\n"
                result += f"  - Hasta: {observaciones_creadas[0]['timestamp']}\n"
                result += f"• Rango de valores: {min(o['valor'] for o in observaciones_creadas):.1f}°C - {max(o['valor'] for o in observaciones_creadas):.1f}°C\n"
            
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