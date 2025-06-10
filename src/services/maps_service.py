"""Servicio de mapas actualizado"""

import logging
from typing import List, Dict, Any, Tuple
import folium
import overpy
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests

from config import settings

logger = logging.getLogger(__name__)

class MapsService:
    """Servicio de mapas con integración OpenStreetMap"""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="mcp_gis_system_v2")
        self.overpass_api = overpy.Overpass()
    
    async def geocode_address(self, address: str) -> Tuple[float, float]:
        """Geocodificar dirección usando Nominatim"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None, 
                lambda: self.geolocator.geocode(address, timeout=10)
            )
            if location:
                return location.latitude, location.longitude
            else:
                raise ValueError(f"No se pudo geocodificar la dirección: {address}")
        except Exception as e:
            logger.error(f"Error en geocodificación: {e}")
            raise
    
    async def find_facilities_nearby(
        self, 
        lat: float, 
        lon: float, 
        radius: int = 2000
    ) -> Dict[str, List[Dict]]:
        """Buscar equipamientos públicos cercanos usando Overpass API"""
        facilities = {}
        
        # Construir consulta Overpass
        bbox = f"{lat-0.02},{lon-0.02},{lat+0.02},{lon+0.02}"
        
        for facility_type, config in settings.gis.facility_types.items():
            try:
                query = f"""
                [out:json][timeout:25];
                (
                  node[{config['query']}]({bbox});
                  way[{config['query']}]({bbox});
                  relation[{config['query']}]({bbox});
                );
                out center;
                """
                
                result = self.overpass_api.query(query)
                facility_list = []
                
                # Procesar nodos
                for node in result.nodes:
                    distance = geodesic((lat, lon), (node.lat, node.lon)).meters
                    if distance <= radius:
                        facility_list.append({
                            'name': node.tags.get('name', f'{config["name"]} sin nombre'),
                            'lat': node.lat,
                            'lon': node.lon,
                            'distance': round(distance),
                            'type': facility_type,
                            'address': node.tags.get('addr:full', 
                                     f"{node.tags.get('addr:street', '')} {node.tags.get('addr:housenumber', '')}").strip(),
                            'phone': node.tags.get('phone', ''),
                            'website': node.tags.get('website', ''),
                            'opening_hours': node.tags.get('opening_hours', '')
                        })
                
                # Procesar ways (edificios)
                for way in result.ways:
                    if way.center_lat and way.center_lon:
                        distance = geodesic((lat, lon), (way.center_lat, way.center_lon)).meters
                        if distance <= radius:
                            facility_list.append({
                                'name': way.tags.get('name', f'{config["name"]} sin nombre'),
                                'lat': way.center_lat,
                                'lon': way.center_lon,
                                'distance': round(distance),
                                'type': facility_type,
                                'address': way.tags.get('addr:full',
                                         f"{way.tags.get('addr:street', '')} {way.tags.get('addr:housenumber', '')}").strip(),
                                'phone': way.tags.get('phone', ''),
                                'website': way.tags.get('website', ''),
                                'opening_hours': way.tags.get('opening_hours', '')
                            })
                
                # Ordenar por distancia y tomar los 5 más cercanos
                facility_list.sort(key=lambda x: x['distance'])
                facilities[facility_type] = facility_list[:5]
                
                logger.info(f"Encontrados {len(facility_list)} {config['name']}s")
                
            except Exception as e:
                logger.error(f"Error buscando {facility_type}: {e}")
                facilities[facility_type] = []
        
        return facilities
    
    async def create_interactive_map(
        self,
        address: str,
        lat: float,
        lon: float,
        facilities: Dict[str, List[Dict]],
        show_census_sections: bool = False
    ) -> str:
        """Crear mapa interactivo con equipamientos y opcionalmente secciones censales"""
        
        # Crear mapa centrado en la dirección
        m = folium.Map(
            location=[lat, lon],
            zoom_start=14,
            tiles='OpenStreetMap'
        )
        
        # Añadir marcador de la dirección buscada
        folium.Marker(
            [lat, lon],
            popup=f"<b>Dirección buscada:</b><br>{address}",
            tooltip="Tu ubicación",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Añadir marcadores de equipamientos
        for facility_type, facility_list in facilities.items():
            if facility_list:
                config = settings.gis.facility_types[facility_type]
                
                for facility in facility_list:
                    popup_html = f"""
                    <div style="width:200px">
                        <h4>{facility['name']}</h4>
                        <p><b>Tipo:</b> {config['name']}</p>
                        <p><b>Distancia:</b> {facility['distance']} metros</p>
                        <p><b>Dirección:</b> {facility['address'] or 'No disponible'}</p>
                        <p><b>Teléfono:</b> {facility['phone'] or 'No disponible'}</p>
                        <p><b>Horario:</b> {facility['opening_hours'] or 'No disponible'}</p>
                        {f'<p><b>Web:</b> <a href="{facility["website"]}" target="_blank">Ver</a></p>' if facility['website'] else ''}
                    </div>
                    """
                    
                    folium.Marker(
                        [facility['lat'], facility['lon']],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"{facility['name']} ({facility['distance']}m)",
                        icon=folium.Icon(
                            color=config['color'],
                            icon=config['icon'],
                            prefix='fa'
                        )
                    ).add_to(m)
        
        # Añadir leyenda
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 200px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>Equipamientos Públicos</h4>
        '''
        
        for facility_type, config in settings.gis.facility_types.items():
            legend_html += f'<p><i class="fa fa-{config["icon"]}" style="color:{config["color"]}"></i> {config["name"]}</p>'
        
        legend_html += '</div>'
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Guardar mapa
        map_filename = f"mapa_{lat}_{lon}.html"
        map_path = settings.paths.maps_dir / map_filename
        m.save(str(map_path))
        
        logger.info(f"Mapa interactivo guardado en: {map_path}")
        return map_filename