"""Servidor MCP para análisis GIS y secciones censales"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Configurar path para importaciones
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Importaciones del proyecto (ahora absolutas)
from services.gis_service import GISService
from services.maps_service import MapsService
from database import postgres_client
from config import settings

# Importaciones MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Inicializar servicios
gis_service = GISService()
maps_service = MapsService()

# Crear servidor MCP
app = Server("gis-server-v2")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Listar herramientas GIS disponibles"""
    return [
        Tool(
            name="initialize_gis",
            description="Inicializar conexión a PostgreSQL y servicios GIS",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_census_sections",
            description="Obtener secciones censales con filtros opcionales",
            inputSchema={
                "type": "object",
                "properties": {
                    "municipio": {
                        "type": "string",
                        "description": "Nombre del municipio (opcional)"
                    },
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Bounding box [xmin, ymin, xmax, ymax] (opcional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="spatial_analysis_facilities",
            description="Análisis espacial entre equipamientos y secciones censales",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Dirección para buscar equipamientos cercanos"
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Radio de búsqueda en metros",
                        "default": 2000
                    },
                    "buffer_meters": {
                        "type": "integer", 
                        "description": "Buffer en metros para análisis espacial",
                        "default": 500
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="analyze_facility_coverage",
            description="Analizar cobertura de un tipo de equipamiento",
            inputSchema={
                "type": "object",
                "properties": {
                    "facility_type": {
                        "type": "string",
                        "enum": list(settings.gis.facility_types.keys()),
                        "description": "Tipo de equipamiento a analizar"
                    },
                    "max_distance_meters": {
                        "type": "integer",
                        "description": "Distancia máxima de cobertura en metros",
                        "default": 1000
                    },
                    "municipio": {
                        "type": "string",
                        "description": "Municipio específico (opcional)"
                    }
                },
                "required": ["facility_type"]
            }
        ),
        Tool(
            name="find_optimal_locations",
            description="Encontrar ubicaciones óptimas para nuevos equipamientos",
            inputSchema={
                "type": "object",
                "properties": {
                    "facility_type": {
                        "type": "string",
                        "enum": list(settings.gis.facility_types.keys()),
                        "description": "Tipo de equipamiento"
                    },
                    "num_locations": {
                        "type": "integer",
                        "description": "Número de ubicaciones a sugerir",
                        "default": 3
                    }
                },
                "required": ["facility_type"]
            }
        ),
        Tool(
            name="create_coverage_map",
            description="Crear mapa de cobertura de equipamientos con secciones censales",
            inputSchema={
                "type": "object",
                "properties": {
                    "facility_type": {
                        "type": "string", 
                        "enum": list(settings.gis.facility_types.keys()),
                        "description": "Tipo de equipamiento"
                    },
                    "center_address": {
                        "type": "string",
                        "description": "Dirección central para el mapa"
                    },
                    "show_sections": {
                        "type": "boolean",
                        "description": "Mostrar secciones censales",
                        "default": True
                    }
                },
                "required": ["facility_type", "center_address"]
            }
        ),
        Tool(
            name="generate_accessibility_report",
            description="Generar informe completo de accesibilidad a equipamientos",
            inputSchema={
                "type": "object",
                "properties": {
                    "municipio": {
                        "type": "string",
                        "description": "Municipio para el análisis"
                    },
                    "facility_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(settings.gis.facility_types.keys())
                        },
                        "description": "Tipos de equipamientos a analizar (opcional)"
                    }
                },
                "required": ["municipio"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Ejecutar herramientas GIS"""
    
    try:
        if name == "initialize_gis":
            await postgres_client.initialize()
            return [TextContent(
                type="text",
                text="✅ Servicios GIS y conexión PostgreSQL inicializados correctamente"
            )]
        
        elif name == "get_census_sections":
            municipio = arguments.get("municipio")
            bbox = arguments.get("bbox")
            
            if bbox and len(bbox) == 4:
                bbox = tuple(bbox)
            else:
                bbox = None
            
            sections = await gis_service.get_census_sections(bbox, municipio)
            
            if not sections.empty:
                result = f"📍 **Secciones censales encontradas:** {len(sections)}\n\n"
                
                # Estadísticas generales
                total_pop = sections['poblacion'].sum()
                avg_density = sections['densidad_hab_km2'].mean()
                total_area = sections['superficie_km2'].sum()
                
                result += f"📊 **Estadísticas generales:**\n"
                result += f"• Población total: {total_pop:,} habitantes\n"
                result += f"• Densidad promedio: {avg_density:.1f} hab/km²\n"
                result += f"• Superficie total: {total_area:.2f} km²\n\n"
                
                # Top 5 secciones por población
                top_sections = sections.nlargest(5, 'poblacion')
                result += f"🏘️ **Top 5 secciones por población:**\n"
                for idx, section in top_sections.iterrows():
                    result += f"• {section['codigo_seccion']}: {section['poblacion']:,} hab ({section['nombre_municipio']})\n"
                
            else:
                result = "📍 No se encontraron secciones censales con los criterios especificados"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "spatial_analysis_facilities":
            address = arguments.get("address")
            radius = arguments.get("radius", 2000)
            buffer_meters = arguments.get("buffer_meters", 500)
            
            # Geocodificar dirección
            lat, lon = await maps_service.geocode_address(address)
            
            # Buscar equipamientos cercanos
            facilities = await maps_service.find_facilities_nearby(lat, lon, radius)
            
            # Convertir a lista plana para análisis espacial
            all_facilities = []
            for facility_type, facility_list in facilities.items():
                all_facilities.extend(facility_list)
            
            if all_facilities:
                # Realizar análisis espacial
                spatial_results = await gis_service.spatial_join_facilities_sections(
                    all_facilities, buffer_meters
                )
                
                result = f"🗺️ **Análisis espacial para:** {address}\n"
                result += f"📍 Coordenadas: {lat:.6f}, {lon:.6f}\n"
                result += f"🎯 Radio búsqueda: {radius}m, Buffer análisis: {buffer_meters}m\n\n"
                
                result += f"🏢 **Equipamientos encontrados:** {len(all_facilities)}\n"
                result += f"📊 **Intersecciones con secciones:** {len(spatial_results)}\n\n"
                
                if spatial_results:
                    # Agrupar por sección censal
                    sections_summary = {}
                    for sr in spatial_results:
                        section_code = sr['codigo_seccion']
                        if section_code not in sections_summary:
                            sections_summary[section_code] = {
                                'codigo': section_code,
                                'municipio': sr['nombre_municipio'],
                                'poblacion': sr['poblacion'],
                                'densidad': sr['densidad_hab_km2'],
                                'equipamientos': []
                            }
                        
                        sections_summary[section_code]['equipamientos'].append({
                            'nombre': sr['facility_name'],
                            'tipo': sr['facility_type'],
                            'distancia': sr['distance_to_section_meters']
                        })
                    
                    result += "🏘️ **Secciones censales afectadas:**\n"
                    for section_data in list(sections_summary.values())[:5]:  # Top 5
                        result += f"• **{section_data['codigo']}** ({section_data['municipio']})\n"
                        result += f"  Población: {section_data['poblacion']:,} hab, Densidad: {section_data['densidad']:.1f} hab/km²\n"
                        result += f"  Equipamientos: {len(section_data['equipamientos'])}\n"
                        for eq in section_data['equipamientos'][:3]:  # Top 3 equipamientos
                            result += f"    - {eq['nombre']} ({eq['tipo']}, {eq['distancia']:.0f}m)\n"
                        result += "\n"
            else:
                result = f"⚠️ No se encontraron equipamientos cerca de {address}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "analyze_facility_coverage":
            facility_type = arguments.get("facility_type")
            max_distance = arguments.get("max_distance_meters", 1000)
            municipio = arguments.get("municipio")
            
            coverage_stats = await gis_service.analyze_facility_coverage(
                facility_type, max_distance, municipio
            )
            
            if coverage_stats:
                config = settings.gis.facility_types[facility_type]
                result = f"📊 **Análisis de cobertura - {config['name']}**\n\n"
                
                result += f"🎯 **Parámetros:**\n"
                result += f"• Distancia máxima: {max_distance}m\n"
                result += f"• Municipio: {municipio or 'Todos'}\n\n"
                
                result += f"📈 **Resultados:**\n"
                result += f"• Secciones totales: {coverage_stats.get('total_secciones', 0)}\n"
                result += f"• Secciones con cobertura: {coverage_stats.get('secciones_con_cobertura', 0)}\n"
                result += f"• % Secciones cubiertas: {coverage_stats.get('porcentaje_secciones_cubiertas', 0)}%\n\n"
                
                result += f"👥 **Población:**\n"
                result += f"• Población total: {coverage_stats.get('poblacion_total', 0):,} hab\n"
                result += f"• Población cubierta: {coverage_stats.get('poblacion_cubierta', 0):,} hab\n"
                result += f"• % Población cubierta: {coverage_stats.get('porcentaje_poblacion_cubierta', 0)}%\n\n"
                
                calificacion = coverage_stats.get('calificacion_cobertura', 'desconocida')
                result += f"🏆 **Calificación:** {calificacion.upper()}\n\n"
                
                recomendaciones = coverage_stats.get('recomendaciones', [])
                if recomendaciones:
                    result += f"💡 **Recomendaciones:**\n"
                    for rec in recomendaciones:
                        result += f"• {rec}\n"
            else:
                result = f"❌ No se pudo realizar el análisis de cobertura para {facility_type}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "find_optimal_locations":
            facility_type = arguments.get("facility_type")
            num_locations = arguments.get("num_locations", 3)
            
            optimal_locations = await gis_service.find_optimal_locations(
                facility_type, num_locations
            )
            
            if optimal_locations:
                config = settings.gis.facility_types[facility_type]
                result = f"🎯 **Ubicaciones óptimas para {config['name']}**\n\n"
                
                for i, location in enumerate(optimal_locations, 1):
                    result += f"**{i}. Sección {location['codigo_seccion']}**\n"
                    result += f"📍 Coordenadas: {location['lat']:.6f}, {location['lon']:.6f}\n"
                    result += f"👥 Población servida: {location['poblacion_servida']:,} hab\n"
                    result += f"📊 Densidad: {location['densidad']:.1f} hab/km²\n"
                    result += f"⭐ Score ubicación: {location['score_ubicacion']}\n"
                    result += f"💭 Justificación: {location['justificacion']}\n\n"
            else:
                result = f"⚠️ No se encontraron ubicaciones óptimas para {facility_type}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "create_coverage_map":
            facility_type = arguments.get("facility_type")
            center_address = arguments.get("center_address")
            show_sections = arguments.get("show_sections", True)
            
            # Geocodificar dirección central
            center_lat, center_lon = await maps_service.geocode_address(center_address)
            
            # Crear mapa de cobertura
            map_filename = await gis_service.create_coverage_map(
                facility_type, center_lat, center_lon, 
                show_sections=show_sections
            )
            
            config = settings.gis.facility_types[facility_type]
            result = f"🗺️ **Mapa de cobertura creado**\n\n"
            result += f"📍 Centro: {center_address} ({center_lat:.6f}, {center_lon:.6f})\n"
            result += f"🏢 Tipo: {config['name']}\n"
            result += f"📊 Secciones censales: {'Sí' if show_sections else 'No'}\n"
            result += f"🔗 Archivo: {map_filename}\n"
            result += f"🌐 URL: http://{settings.api.host}:{settings.api.port}/map/{map_filename}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "generate_accessibility_report":
            municipio = arguments.get("municipio")
            facility_types = arguments.get("facility_types")
            
            report = await gis_service.generate_accessibility_report(
                municipio, facility_types
            )
            
            result = f"📋 **Informe de Accesibilidad - {municipio}**\n"
            result += f"📅 Fecha: {report['fecha_analisis'][:10]}\n"
            result += f"🏢 Equipamientos analizados: {len(report['equipamientos_analizados'])}\n\n"
            
            # Resumen ejecutivo
            summary = report['resumen_ejecutivo']
            result += f"📊 **Resumen Ejecutivo:**\n"
            result += f"• Cobertura promedio: {summary['cobertura_promedio']}%\n"
            result += f"• Equipamientos críticos: {len(summary['equipamientos_criticos'])}\n\n"
            
            if summary['equipamientos_criticos']:
                result += f"🚨 **Equipamientos críticos (cobertura < 50%):**\n"
                for eq in summary['equipamientos_criticos']:
                    result += f"• {eq['tipo']}: {eq['cobertura']:.1f}% cobertura\n"
                result += "\n"
            
            if summary['recomendaciones_prioritarias']:
                result += f"💡 **Recomendaciones prioritarias:**\n"
                for rec in summary['recomendaciones_prioritarias']:
                    result += f"• {rec}\n"
                result += "\n"
            
            # Detalle por equipamiento
            result += f"📈 **Detalle por equipamiento:**\n"
            for eq_type, data in report['resultados'].items():
                config = settings.gis.facility_types[eq_type]
                cobertura = data['cobertura']
                result += f"**{config['name']}:** {cobertura.get('porcentaje_poblacion_cubierta', 0):.1f}% población cubierta\n"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"❌ Herramienta desconocida: {name}")]
    
    except Exception as e:
        logger.error(f"Error en herramienta GIS {name}: {e}")
        return [TextContent(type="text", text=f"❌ Error ejecutando {name}: {str(e)}")]

async def main():
    """Función principal del servidor GIS"""
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())