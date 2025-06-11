"""
Servicio TimescaleDB para gestión de sensores, observaciones y alertas
Implementa la funcionalidad específica de la versión ampliada
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium import plugins
import asyncio

from config import settings
from database import postgres_client
from utils.geocoding import GeocodingService

logger = logging.getLogger(__name__)

class TimescaleService:
    """Servicio para operaciones con TimescaleDB y datos de sensores"""
    
    def __init__(self):
        self.postgres_client = postgres_client
        self.geocoding = GeocodingService()
    
    async def get_sensores_activos(self, tipo_sensor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtener lista de sensores activos"""
        try:
            base_query = """
            SELECT 
                s.id,
                s.nombre,
                s.tipo_sensor,
                s.estado,
                s.unidad_medida,
                ST_X(s.localizacion::geometry) as lon,
                ST_Y(s.localizacion::geometry) as lat,
                s.fabricante,
                s.modelo,
                s.frecuencia_envio,
                -- Estadísticas de la última hora
                COUNT(o.id) as observaciones_ultima_hora,
                ROUND(AVG(o.valor), 2) as valor_promedio,
                MAX(o.fecha_observacion) as ultima_observacion,
                ROUND(AVG(o.nivel_bateria), 1) as bateria_promedio
            FROM sensores s
            LEFT JOIN observaciones o ON s.id = o.sensor_id 
                AND o.fecha_observacion >= NOW() - INTERVAL '1 hour'
            WHERE s.estado = 'activo'
            """
            
            params = {}
            if tipo_sensor:
                base_query += " AND s.tipo_sensor = $1"
                params = {"tipo": tipo_sensor}
            
            base_query += """
            GROUP BY s.id, s.nombre, s.tipo_sensor, s.estado, s.unidad_medida, 
                     s.localizacion, s.fabricante, s.modelo, s.frecuencia_envio
            ORDER BY s.nombre
            """
            
            result = await self.postgres_client.execute_query(base_query, params)
            
            logger.info(f"Obtenidos {len(result)} sensores activos")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo sensores activos: {e}")
            raise
    
    async def insertar_observacion(
        self,
        sensor_id: int,
        valor: float,
        unidad: str = "°C",
        fecha_observacion: Optional[datetime] = None,
        calidad_dato: str = "buena",
        metadatos: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Insertar nueva observación de sensor"""
        try:
            if fecha_observacion is None:
                fecha_observacion = datetime.utcnow()
            
            if metadatos is None:
                metadatos = {}
            
            query = """
            INSERT INTO observaciones (
                sensor_id, valor, unidad, fecha_observacion, calidad_dato,
                temperatura_ambiente, humedad_ambiente, nivel_bateria, intensidad_senal
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """
            
            params = {
                "sensor_id": sensor_id,
                "valor": valor,
                "unidad": unidad,
                "fecha_observacion": fecha_observacion,
                "calidad_dato": calidad_dato,
                "temp_ambiente": metadatos.get("temperatura_ambiente"),
                "humedad": metadatos.get("humedad_ambiente"),
                "bateria": metadatos.get("nivel_bateria"),
                "senal": metadatos.get("intensidad_senal")
            }
            
            await self.postgres_client.execute_command(query, params)
            
            logger.info(f"Observación insertada para sensor {sensor_id}: {valor} {unidad}")
            return True
            
        except Exception as e:
            logger.error(f"Error insertando observación: {e}")
            raise
    
    async def get_observaciones_recientes(
        self,
        sensor_id: Optional[int] = None,
        horas_atras: int = 24,
        limite: int = 1000
    ) -> List[Dict[str, Any]]:
        """Obtener observaciones recientes"""
        try:
            base_query = """
            SELECT 
                o.id,
                o.sensor_id,
                s.nombre as sensor_nombre,
                o.valor,
                o.unidad,
                o.fecha_observacion,
                o.calidad_dato,
                o.nivel_bateria,
                o.intensidad_senal,
                ST_X(o.localizacion::geometry) as lon,
                ST_Y(o.localizacion::geometry) as lat
            FROM observaciones o
            JOIN sensores s ON o.sensor_id = s.id
            WHERE o.fecha_observacion >= NOW() - INTERVAL '{} hours'
            """.format(horas_atras)
            
            params = {}
            if sensor_id:
                base_query += " AND o.sensor_id = $1"
                params = {"sensor_id": sensor_id}
            
            base_query += """
            ORDER BY o.fecha_observacion DESC
            LIMIT {}
            """.format(limite)
            
            result = await self.postgres_client.execute_query(base_query, params)
            
            logger.info(f"Obtenidas {len(result)} observaciones recientes")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo observaciones recientes: {e}")
            raise
    
    async def get_agregados_horarios(
        self,
        sensor_id: int,
        horas_atras: int = 48
    ) -> List[Dict[str, Any]]:
        """Obtener agregados horarios de un sensor"""
        try:
            query = """
            SELECT 
                hora,
                sensor_id,
                ROUND(temp_media, 2) as temp_media,
                ROUND(temp_min, 2) as temp_min,
                ROUND(temp_max, 2) as temp_max,
                num_observaciones,
                ROUND(desviacion_estandar, 2) as desviacion_estandar
            FROM temp_horaria
            WHERE sensor_id = $1
            AND hora >= NOW() - INTERVAL '{} hours'
            ORDER BY hora DESC
            """.format(horas_atras)
            
            result = await self.postgres_client.execute_query(
                query, 
                {"sensor_id": sensor_id}
            )
            
            logger.info(f"Obtenidos {len(result)} agregados horarios para sensor {sensor_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo agregados horarios: {e}")
            raise
    
    async def get_alertas_activas(
        self,
        severidad: Optional[str] = None,
        tipo_alerta: Optional[str] = None,
        limite: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtener alertas activas"""
        try:
            base_query = """
            SELECT 
                a.id,
                a.sensor_id,
                s.nombre as sensor_nombre,
                a.refugio_id,
                r.nombre as refugio_nombre,
                a.tipo_alerta,
                a.severidad,
                a.valor_actual,
                a.umbral_configurado,
                a.fecha_deteccion,
                a.mensaje_alerta,
                a.sms_enviado,
                a.email_enviado,
                ST_X(s.localizacion::geometry) as sensor_lon,
                ST_Y(s.localizacion::geometry) as sensor_lat,
                ST_X(r.geom::geometry) as refugio_lon,
                ST_Y(r.geom::geometry) as refugio_lat
            FROM alertas_temperatura a
            JOIN sensores s ON a.sensor_id = s.id
            LEFT JOIN refugios r ON a.refugio_id = r.id
            WHERE a.estado = 'activa'
            """
            
            params = {}
            filter_count = 0
            
            if severidad:
                filter_count += 1
                base_query += f" AND a.severidad = ${filter_count}"
                params[f"param{filter_count}"] = severidad
            
            if tipo_alerta:
                filter_count += 1
                base_query += f" AND a.tipo_alerta = ${filter_count}"
                params[f"param{filter_count}"] = tipo_alerta
            
            base_query += f"""
            ORDER BY 
                CASE a.severidad 
                    WHEN 'critica' THEN 1
                    WHEN 'alta' THEN 2
                    WHEN 'media' THEN 3
                    ELSE 4
                END,
                a.fecha_deteccion DESC
            LIMIT {limite}
            """
            
            result = await self.postgres_client.execute_query(base_query, params)
            
            logger.info(f"Obtenidas {len(result)} alertas activas")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo alertas activas: {e}")
            raise
    
    async def resolver_alerta(self, alerta_id: str, usuario: str = "sistema") -> bool:
        """Resolver una alerta activa"""
        try:
            query = """
            UPDATE alertas_temperatura 
            SET estado = 'resuelta',
                fecha_resolucion = NOW(),
                personal_notificado = CONCAT(
                    COALESCE(personal_notificado, ''), 
                    '; Resuelto por: ', $2, ' el ', NOW()
                )
            WHERE id = $1 AND estado = 'activa'
            """
            
            result = await self.postgres_client.execute_command(
                query, 
                {"alerta_id": alerta_id, "usuario": usuario}
            )
            
            logger.info(f"Alerta {alerta_id} resuelta por {usuario}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolviendo alerta {alerta_id}: {e}")
            raise
    
    async def get_refugios_cercanos(
        self,
        lat: float,
        lon: float,
        radio_km: float = 10.0,
        incluir_llenos: bool = False
    ) -> List[Dict[str, Any]]:
        """Obtener refugios cercanos a una ubicación"""
        try:
            query = """
            SELECT 
                r.id,
                r.nombre,
                r.tipo_refugio,
                r.estado_operativo,
                r.capacidad_maxima,
                r.capacidad_actual,
                ROUND((r.capacidad_actual::FLOAT / r.capacidad_maxima::FLOAT * 100), 1) as porcentaje_ocupacion,
                r.tiene_aire_acondicionado,
                r.tiene_calefaccion,
                r.tiene_servicio_medico,
                r.telefono,
                r.responsable,
                ST_X(r.geom::geometry) as lon,
                ST_Y(r.geom::geometry) as lat,
                ROUND(
                    ST_Distance(
                        r.geom::geography,
                        ST_Point($2, $1)::geography
                    ) / 1000, 2
                ) as distancia_km
            FROM refugios r
            WHERE ST_DWithin(
                r.geom::geography,
                ST_Point($2, $1)::geography,
                $3 * 1000
            )
            """
            
            params = {"lat": lat, "lon": lon, "radio": radio_km}
            
            if not incluir_llenos:
                query += " AND r.capacidad_actual < r.capacidad_maxima"
            
            query += " ORDER BY distancia_km"
            
            result = await self.postgres_client.execute_query(query, params)
            
            logger.info(f"Encontrados {len(result)} refugios cercanos")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo refugios cercanos: {e}")
            raise
    
    async def calcular_ruta_refugio(
        self,
        sensor_id: int,
        refugio_id: int
    ) -> List[Dict[str, Any]]:
        """Calcular ruta óptima desde sensor hasta refugio"""
        try:
            # Obtener coordenadas del sensor
            sensor_query = """
            SELECT ST_X(localizacion::geometry) as lon, ST_Y(localizacion::geometry) as lat
            FROM sensores WHERE id = $1
            """
            sensor_result = await self.postgres_client.execute_query(
                sensor_query, {"sensor_id": sensor_id}
            )
            
            if not sensor_result:
                raise ValueError(f"Sensor {sensor_id} no encontrado")
            
            sensor_coords = sensor_result[0]
            
            # Calcular ruta usando la función PL/pgSQL
            ruta_query = """
            SELECT step_seq, edge_id, cost, geojson
            FROM calcular_ruta_refugio($1, $2, $3)
            """
            
            ruta_result = await self.postgres_client.execute_query(
                ruta_query, {
                    "lat": sensor_coords["lat"],
                    "lon": sensor_coords["lon"], 
                    "refugio_id": refugio_id
                }
            )
            
            logger.info(f"Ruta calculada: {len(ruta_result)} segmentos")
            return ruta_result
            
        except Exception as e:
            logger.error(f"Error calculando ruta: {e}")
            raise
    
    async def crear_mapa_alertas(
        self,
        centro_lat: float = 40.4168,
        centro_lon: float = -3.7038,
        zoom: int = 10,
        incluir_rutas: bool = True
    ) -> str:
        """Crear mapa con alertas, sensores y refugios"""
        try:
            # Crear mapa base
            m = folium.Map(
                location=[centro_lat, centro_lon],
                zoom_start=zoom,
                tiles='OpenStreetMap'
            )
            
            # Obtener alertas activas
            alertas = await self.get_alertas_activas()
            
            # Obtener sensores activos
            sensores = await self.get_sensores_activos()
            
            # Obtener refugios cercanos
            refugios = await self.get_refugios_cercanos(
                centro_lat, centro_lon, radio_km=50
            )
            
            # Añadir sensores al mapa
            for sensor in sensores:
                # Verificar si tiene alertas
                sensor_alertas = [a for a in alertas if a['sensor_id'] == sensor['id']]
                
                if sensor_alertas:
                    # Sensor con alerta
                    alerta = sensor_alertas[0]  # Tomar la más crítica
                    color = {
                        'critica': 'red',
                        'alta': 'orange', 
                        'media': 'yellow',
                        'baja': 'blue'
                    }.get(alerta['severidad'], 'gray')
                    
                    popup_html = f"""
                    <div style="width:250px">
                        <h4>🚨 {sensor['nombre']}</h4>
                        <p><b>Alerta:</b> {alerta['tipo_alerta']}</p>
                        <p><b>Severidad:</b> {alerta['severidad']}</p>
                        <p><b>Valor actual:</b> {alerta['valor_actual']}°C</p>
                        <p><b>Umbral:</b> {alerta['umbral_configurado']}°C</p>
                        <p><b>Última observación:</b> {sensor.get('ultima_observacion', 'N/A')}</p>
                    </div>
                    """
                    icon_name = 'exclamation-triangle'
                else:
                    # Sensor normal
                    color = 'green'
                    popup_html = f"""
                    <div style="width:200px">
                        <h4>📡 {sensor['nombre']}</h4>
                        <p><b>Tipo:</b> {sensor['tipo_sensor']}</p>
                        <p><b>Estado:</b> {sensor['estado']}</p>
                        <p><b>Valor promedio:</b> {sensor.get('valor_promedio', 'N/A')}°C</p>
                        <p><b>Batería:</b> {sensor.get('bateria_promedio', 'N/A')}%</p>
                        <p><b>Observaciones:</b> {sensor.get('observaciones_ultima_hora', 0)}</p>
                    </div>
                    """
                    icon_name = 'thermometer-half'
                
                folium.Marker(
                    [sensor['lat'], sensor['lon']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{sensor['nombre']} - {sensor.get('valor_promedio', 'N/A')}°C",
                    icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                ).add_to(m)
            
            # Añadir refugios al mapa
            for refugio in refugios:
                disponibilidad = refugio['capacidad_maxima'] - refugio['capacidad_actual']
                color_refugio = 'green' if disponibilidad > 50 else 'orange' if disponibilidad > 0 else 'red'
                
                popup_html = f"""
                <div style="width:250px">
                    <h4>🏠 {refugio['nombre']}</h4>
                    <p><b>Tipo:</b> {refugio['tipo_refugio']}</p>
                    <p><b>Estado:</b> {refugio['estado_operativo']}</p>
                    <p><b>Capacidad:</b> {refugio['capacidad_actual']}/{refugio['capacidad_maxima']}</p>
                    <p><b>Disponible:</b> {disponibilidad} plazas</p>
                    <p><b>Distancia:</b> {refugio['distancia_km']} km</p>
                    <p><b>Servicios:</b></p>
                    <ul>
                        {'<li>Aire acondicionado</li>' if refugio['tiene_aire_acondicionado'] else ''}
                        {'<li>Calefacción</li>' if refugio['tiene_calefaccion'] else ''}
                        {'<li>Servicio médico</li>' if refugio['tiene_servicio_medico'] else ''}
                    </ul>
                </div>
                """
                
                folium.Marker(
                    [refugio['lat'], refugio['lon']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{refugio['nombre']} - {disponibilidad} plazas",
                    icon=folium.Icon(color=color_refugio, icon='home', prefix='fa')
                ).add_to(m)
            
            # Añadir rutas de evacuación si se solicita
            if incluir_rutas and alertas:
                for alerta in alertas[:5]:  # Máximo 5 rutas
                    if alerta['refugio_id']:
                        try:
                            ruta = await self.calcular_ruta_refugio(
                                alerta['sensor_id'], 
                                alerta['refugio_id']
                            )
                            
                            if ruta:
                                # Crear coordenadas de la ruta
                                ruta_coords = []
                                for segmento in ruta:
                                    # Parsear GeoJSON del segmento
                                    import json
                                    geom = json.loads(segmento['geojson'])
                                    coords = geom['coordinates']
                                    
                                    # Convertir a formato [lat, lon]
                                    for coord in coords:
                                        ruta_coords.append([coord[1], coord[0]])
                                
                                # Añadir ruta al mapa
                                folium.PolyLine(
                                    ruta_coords,
                                    color='red',
                                    weight=4,
                                    opacity=0.8,
                                    popup=f"Ruta evacuación - Sensor {alerta['sensor_id']} → Refugio {alerta['refugio_id']}"
                                ).add_to(m)
                                
                        except Exception as e:
                            logger.warning(f"No se pudo calcular ruta para alerta {alerta['id']}: {e}")
            
            # Añadir leyenda
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; left: 50px; width: 220px; height: 280px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:12px; padding: 10px">
            <h4>🗺️ Leyenda del Mapa</h4>
            <p><i class="fa fa-exclamation-triangle" style="color:red"></i> Sensor con alerta crítica</p>
            <p><i class="fa fa-exclamation-triangle" style="color:orange"></i> Sensor con alerta alta</p>
            <p><i class="fa fa-exclamation-triangle" style="color:yellow"></i> Sensor con alerta media</p>
            <p><i class="fa fa-thermometer-half" style="color:green"></i> Sensor normal</p>
            <p><i class="fa fa-home" style="color:green"></i> Refugio disponible</p>
            <p><i class="fa fa-home" style="color:orange"></i> Refugio con poca capacidad</p>
            <p><i class="fa fa-home" style="color:red"></i> Refugio lleno</p>
            <p style="color:red; font-weight:bold">— Ruta de evacuación</p>
            </div>
            '''
            
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Añadir plugin de pantalla completa
            plugins.Fullscreen().add_to(m)
            
            # Añadir plugin de medición
            plugins.MeasureControl().add_to(m)
            
            # Guardar mapa
            map_filename = f"alertas_sensores_{centro_lat}_{centro_lon}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
            map_path = settings.paths.maps_dir / map_filename
            m.save(str(map_path))
            
            logger.info(f"Mapa de alertas creado: {map_filename}")
            return map_filename
            
        except Exception as e:
            logger.error(f"Error creando mapa de alertas: {e}")
            raise
    
    async def generar_informe_alertas(
        self,
        zona_lat: float,
        zona_lon: float,
        radio_km: float = 10.0,
        periodo_horas: int = 24
    ) -> Dict[str, Any]:
        """Generar informe completo de alertas para una zona"""
        try:
            # Usar función SQL para resumen de zona
            resumen_query = "SELECT * FROM resumen_alertas_zona($1, $2, $3)"
            resumen = await self.postgres_client.execute_query(
                resumen_query, 
                {"lat": zona_lat, "lon": zona_lon, "radio": radio_km}
            )
            
            # Obtener alertas detalladas de la zona
            alertas_query = """
            SELECT 
                a.id,
                a.tipo_alerta,
                a.severidad,
                a.valor_actual,
                a.fecha_deteccion,
                s.nombre as sensor_nombre,
                r.nombre as refugio_nombre,
                ROUND(ST_Distance(
                    s.localizacion::geography,
                    ST_Point($2, $1)::geography
                ) / 1000, 2) as distancia_km
            FROM alertas_temperatura a
            JOIN sensores s ON a.sensor_id = s.id
            LEFT JOIN refugios r ON a.refugio_id = r.id
            WHERE a.estado = 'activa'
            AND a.fecha_deteccion >= NOW() - INTERVAL '{} hours'
            AND ST_DWithin(
                s.localizacion::geography,
                ST_Point($2, $1)::geography,
                $3 * 1000
            )
            ORDER BY a.severidad, a.fecha_deteccion DESC
            """.format(periodo_horas)
            
            alertas_detalle = await self.postgres_client.execute_query(
                alertas_query,
                {"lat": zona_lat, "lon": zona_lon, "radio": radio_km}
            )
            
            # Obtener refugios en la zona
            refugios = await self.get_refugios_cercanos(zona_lat, zona_lon, radio_km)
            
            # Calcular métricas adicionales
            total_capacidad_refugios = sum(r['capacidad_maxima'] for r in refugios)
            capacidad_disponible = sum(
                r['capacidad_maxima'] - r['capacidad_actual'] 
                for r in refugios 
                if r['estado_operativo'] == 'disponible'
            )
            
            # Generar recomendaciones
            recomendaciones = []
            if resumen and resumen[0]['alertas_criticas'] > 0:
                recomendaciones.append("🚨 Activar protocolo de emergencia - Alertas críticas detectadas")
                recomendaciones.append("📢 Notificar a servicios de emergencia")
            
            if resumen and resumen[0]['total_alertas'] > 5:
                recomendaciones.append("⚠️ Alto número de alertas - Considerar evacuación preventiva")
            
            if capacidad_disponible < 100:
                recomendaciones.append("🏠 Capacidad de refugios limitada - Activar refugios adicionales")
            
            if not refugios:
                recomendaciones.append("❌ No hay refugios en el área - Coordinar con zonas cercanas")
            
            # Compilar informe
            informe = {
                "zona": {
                    "centro_lat": zona_lat,
                    "centro_lon": zona_lon,
                    "radio_km": radio_km
                },
                "periodo_analisis": {
                    "horas": periodo_horas,
                    "fecha_inicio": (datetime.now() - timedelta(hours=periodo_horas)).isoformat(),
                    "fecha_fin": datetime.now().isoformat()
                },
                "resumen_alertas": resumen[0] if resumen else {
                    "total_alertas": 0,
                    "alertas_criticas": 0,
                    "alertas_altas": 0,
                    "alertas_medias": 0
                },
                "alertas_detalle": alertas_detalle,
                "refugios_zona": {
                    "total_refugios": len(refugios),
                    "refugios_disponibles": len([r for r in refugios if r['estado_operativo'] == 'disponible']),
                    "capacidad_total": total_capacidad_refugios,
                    "capacidad_disponible": capacidad_disponible,
                    "porcentaje_ocupacion": round(
                        ((total_capacidad_refugios - capacidad_disponible) / total_capacidad_refugios * 100) 
                        if total_capacidad_refugios > 0 else 0, 1
                    ),
                    "detalle_refugios": refugios
                },
                "nivel_riesgo": self._calcular_nivel_riesgo(resumen[0] if resumen else {}, refugios),
                "recomendaciones": recomendaciones,
                "fecha_generacion": datetime.now().isoformat()
            }
            
            logger.info(f"Informe de alertas generado para zona ({zona_lat}, {zona_lon})")
            return informe
            
        except Exception as e:
            logger.error(f"Error generando informe de alertas: {e}")
            raise
    
    def _calcular_nivel_riesgo(
        self, 
        resumen_alertas: Dict[str, Any], 
        refugios: List[Dict[str, Any]]
    ) -> str:
        """Calcular nivel de riesgo basado en alertas y capacidad de refugios"""
        
        alertas_criticas = resumen_alertas.get('alertas_criticas', 0)
        alertas_altas = resumen_alertas.get('alertas_altas', 0)
        total_alertas = resumen_alertas.get('total_alertas', 0)
        
        capacidad_disponible = sum(
            r['capacidad_maxima'] - r['capacidad_actual'] 
            for r in refugios 
            if r['estado_operativo'] == 'disponible'
        )
        
        # Lógica de cálculo de riesgo
        if alertas_criticas >= 3 or (alertas_criticas >= 1 and capacidad_disponible < 50):
            return "CRÍTICO"
        elif alertas_criticas >= 1 or alertas_altas >= 3 or total_alertas >= 10:
            return "ALTO"
        elif alertas_altas >= 1 or total_alertas >= 5:
            return "MEDIO"
        elif total_alertas > 0:
            return "BAJO"
        else:
            return "NORMAL"
    
    async def actualizar_capacidad_refugio(
        self,
        refugio_id: int,
        nueva_capacidad: int,
        usuario: str = "sistema"
    ) -> bool:
        """Actualizar capacidad actual de un refugio"""
        try:
            query = """
            UPDATE refugios 
            SET capacidad_actual = $2,
                updated_at = NOW()
            WHERE id = $1
            AND $2 <= capacidad_maxima
            """
            
            result = await self.postgres_client.execute_command(
                query,
                {"refugio_id": refugio_id, "capacidad": nueva_capacidad}
            )
            
            logger.info(f"Capacidad de refugio {refugio_id} actualizada a {nueva_capacidad} por {usuario}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando capacidad de refugio {refugio_id}: {e}")
            raise
    
    async def get_estadisticas_tiempo_real(self) -> Dict[str, Any]:
        """Obtener estadísticas del sistema en tiempo real"""
        try:
            # Usar vista SQL creada
            stats_query = "SELECT * FROM estadisticas_tiempo_real"
            sensores_stats = await self.postgres_client.execute_query(stats_query)
            
            # Estadísticas de alertas
            alertas_stats_query = """
            SELECT 
                COUNT(*) as total_alertas_activas,
                COUNT(*) FILTER (WHERE severidad = 'critica') as alertas_criticas,
                COUNT(*) FILTER (WHERE severidad = 'alta') as alertas_altas,
                COUNT(*) FILTER (WHERE severidad = 'media') as alertas_medias,
                COUNT(*) FILTER (WHERE sms_enviado = true) as alertas_sms_enviado,
                COUNT(*) FILTER (WHERE fecha_deteccion >= NOW() - INTERVAL '1 hour') as alertas_ultima_hora
            FROM alertas_temperatura
            WHERE estado = 'activa'
            """
            
            alertas_stats = await self.postgres_client.execute_query(alertas_stats_query)
            
            # Estadísticas de refugios
            refugios_stats_query = """
            SELECT 
                COUNT(*) as total_refugios,
                COUNT(*) FILTER (WHERE estado_operativo = 'disponible') as refugios_disponibles,
                SUM(capacidad_maxima) as capacidad_total,
                SUM(capacidad_actual) as ocupacion_actual,
                ROUND(AVG(capacidad_actual::FLOAT / capacidad_maxima::FLOAT * 100), 1) as ocupacion_promedio
            FROM refugios
            """
            
            refugios_stats = await self.postgres_client.execute_query(refugios_stats_query)
            
            # Estadísticas de observaciones
            observaciones_stats_query = """
            SELECT 
                COUNT(*) as observaciones_ultima_hora,
                COUNT(DISTINCT sensor_id) as sensores_activos_ultima_hora,
                ROUND(AVG(valor), 2) as temperatura_promedio,
                ROUND(MIN(valor), 2) as temperatura_minima,
                ROUND(MAX(valor), 2) as temperatura_maxima,
                ROUND(AVG(nivel_bateria), 1) as bateria_promedio
            FROM observaciones
            WHERE fecha_observacion >= NOW() - INTERVAL '1 hour'
            AND unidad = '°C'
            """
            
            observaciones_stats = await self.postgres_client.execute_query(observaciones_stats_query)
            
            # Compilar estadísticas
            estadisticas = {
                "timestamp": datetime.now().isoformat(),
                "sensores": {
                    "total": len(sensores_stats),
                    "activos_ultima_hora": len([s for s in sensores_stats if s['observaciones_ultima_hora'] > 0]),
                    "detalle": sensores_stats
                },
                "alertas": alertas_stats[0] if alertas_stats else {},
                "refugios": refugios_stats[0] if refugios_stats else {},
                "observaciones": observaciones_stats[0] if observaciones_stats else {},
                "sistema": {
                    "estado_general": self._determinar_estado_sistema(
                        alertas_stats[0] if alertas_stats else {},
                        len(sensores_stats)
                    )
                }
            }
            
            return estadisticas
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas tiempo real: {e}")
            raise
    
    def _determinar_estado_sistema(
        self, 
        alertas_stats: Dict[str, Any], 
        total_sensores: int
    ) -> str:
        """Determinar estado general del sistema"""
        
        alertas_criticas = alertas_stats.get('alertas_criticas', 0)
        alertas_altas = alertas_stats.get('alertas_altas', 0)
        total_alertas = alertas_stats.get('total_alertas_activas', 0)
        
        if alertas_criticas > 0:
            return "EMERGENCIA"
        elif alertas_altas >= 3 or total_alertas >= 10:
            return "ALERTA"
        elif total_alertas > 0:
            return "VIGILANCIA"
        elif total_sensores == 0:
            return "SIN_DATOS"
        else:
            return "NORMAL"