"""Servidor MCP para mapas básicos"""

import asyncio
import logging
from typing import List, Dict, Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..services.maps_service import MapsService
from ..config import settings

logger = logging.getLogger(__name__)

# Inicializar servicio de mapas
maps_service = MapsService()

# Crear servidor MCP
app = Server("maps-server-v2")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Listar herramientas de mapas disponibles"""
    return [
        Tool(
            name="geocode_address",
            description="Obtener coordenadas de una dirección",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Dirección a geocodificar"
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="find_nearby_facilities",
            description="Buscar equipamientos públicos cercanos a una dirección",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Dirección de referencia"
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Radio de búsqueda en metros",
                        "default": 2000
                    },
                    "facility_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(settings.gis.facility_types.keys())
                        },
                        "description": "Tipos específicos de equipamientos (opcional)"
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="create_interactive_map",
            description="Crear mapa interactivo con equipamientos cercanos",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Dirección central del mapa"
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Radio de búsqueda en metros",
                        "default": 1500
                    },
                    "include_census": {
                        "type": "boolean",
                        "description": "Incluir secciones censales",
                        "default": False
                    }
                },
                "required": ["address"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Ejecutar herramientas de mapas"""
    
    try:
        if name == "geocode_address":
            address = arguments.get("address")
            
            lat, lon = await maps_service.geocode_address(address)
            
            result = f"📍 **Geocodificación exitosa**\n"
            result += f"Dirección: {address}\n"
            result += f"Coordenadas: {lat:.6f}, {lon:.6f}\n"
            result += f"Google Maps: https://maps.google.com/?q={lat},{lon}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "find_nearby_facilities":
            address = arguments.get("address")
            radius = arguments.get("radius", 2000)
            specific_types = arguments.get("facility_types", [])
            
            # Geocodificar dirección
            lat, lon = await maps_service.geocode_address(address)
            
            # Buscar equipamientos
            all_facilities = await maps_service.find_facilities_nearby(lat, lon, radius)
            
            # Filtrar tipos específicos si se especificaron
            if specific_types:
                filtered_facilities = {
                    k: v for k, v in all_facilities.items() 
                    if k in specific_types
                }
            else:
                filtered_facilities = all_facilities
            
            # Contar total de equipamientos
            total_count = sum(len(facilities) for facilities in filtered_facilities.values())
            
            result = f"🎯 **Equipamientos cerca de:** {address}\n"
            result += f"📍 Coordenadas: {lat:.6f}, {lon:.6f}\n"
            result += f"📏 Radio búsqueda: {radius}m\n"
            result += f"🏢 Total encontrados: {total_count}\n\n"
            
            if total_count > 0:
                for facility_type, facilities in filtered_facilities.items():
                    if facilities:
                        config = settings.gis.facility_types[facility_type]
                        result += f"**{config['name']}s ({len(facilities)}):**\n"
                        
                        for facility in facilities:
                            result += f"• {facility['name']} - {facility['distance']}m\n"
                            if facility['address']:
                                result += f"  📍 {facility['address']}\n"
                            if facility['phone']:
                                result += f"  📞 {facility['phone']}\n"
                        result += "\n"
            else:
                result += "⚠️ No se encontraron equipamientos en el radio especificado"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "create_interactive_map":
            address = arguments.get("address")
            radius = arguments.get("radius", 1500)
            include_census = arguments.get("include_census", False)
            
            # Geocodificar dirección
            lat, lon = await maps_service.geocode_address(address)
            
            # Buscar equipamientos
            facilities = await maps_service.find_facilities_nearby(lat, lon, radius)
            
            # Crear mapa
            map_filename = await maps_service.create_interactive_map(
                address, lat, lon, facilities, include_census
            )
            
            # Contar equipamientos
            total_facilities = sum(len(f_list) for f_list in facilities.values())
            
            result = f"🗺️ **Mapa interactivo creado**\n\n"
            result += f"📍 Centro: {address}\n"
            result += f"📏 Radio: {radius}m\n"
            result += f"🏢 Equipamientos: {total_facilities}\n"
            result += f"📊 Secciones censales: {'Incluidas' if include_census else 'No incluidas'}\n"
            result += f"📄 Archivo: {map_filename}\n"
            result += f"🌐 Ver mapa: http://{settings.api.host}:{settings.api.port}/map/{map_filename}\n\n"
            
            # Resumen de equipamientos
            if total_facilities > 0:
                result += "📋 **Resumen de equipamientos:**\n"
                for facility_type, facility_list in facilities.items():
                    if facility_list:
                        config = settings.gis.facility_types[facility_type]
                        closest = min(facility_list, key=lambda x: x['distance'])
                        result += f"• {config['name']}: {len(facility_list)} (más cercano: {closest['distance']}m)\n"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"❌ Herramienta desconocida: {name}")]
    
    except Exception as e:
        logger.error(f"Error en herramienta de mapas {name}: {e}")
        return [TextContent(type="text", text=f"❌ Error ejecutando {name}: {str(e)}")]

async def main():
    """Función principal del servidor de mapas"""
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())