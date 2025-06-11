"""
Servicio Twilio para envío de SMS y alertas
Implementa la funcionalidad de notificaciones del sistema ampliado
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import os
import asyncio
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from config import settings

logger = logging.getLogger(__name__)

class TwilioService:
    """Servicio para envío de SMS y notificaciones vía Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER")
        self.client = None
        
        # Verificar configuración
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Configuración de Twilio incompleta. SMS deshabilitado.")
            self.enabled = False
        else:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                self.enabled = True
                logger.info("Servicio Twilio inicializado correctamente")
            except Exception as e:
                logger.error(f"Error inicializando Twilio: {e}")
                self.enabled = False
    
    async def send_sms(
        self, 
        to_number: str, 
        message: str,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Enviar SMS a un número específico
        
        Args:
            to_number: Número de teléfono destino (formato internacional)
            message: Mensaje a enviar
            priority: Prioridad del mensaje (normal, high, urgent)
            
        Returns:
            SID del mensaje si fue exitoso, None si falló
        """
        if not self.enabled:
            logger.warning("Twilio no configurado, simulando envío de SMS")
            logger.info(f"SMS simulado a {to_number}: {message}")
            return f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Validar número de teléfono
            if not to_number.startswith('+'):
                to_number = '+' + to_number.lstrip('+')
            
            # Truncar mensaje si es muy largo
            if len(message) > 1600:
                message = message[:1550] + "... [TRUNCADO]"
            
            # Ejecutar en thread pool para no bloquear
            loop = asyncio.get_event_loop()
            twilio_message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to_number
                )
            )
            
            logger.info(f"SMS enviado exitosamente a {to_number}. SID: {twilio_message.sid}")
            return twilio_message.sid
            
        except TwilioException as e:
            logger.error(f"Error de Twilio enviando SMS a {to_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error general enviando SMS a {to_number}: {e}")
            return None
    
    async def send_sms_bulk(
        self, 
        recipients: List[str], 
        message: str,
        max_concurrent: int = 5
    ) -> Dict[str, Optional[str]]:
        """
        Enviar SMS a múltiples destinatarios de forma concurrente
        
        Args:
            recipients: Lista de números de teléfono
            message: Mensaje a enviar
            max_concurrent: Máximo número de envíos concurrentes
            
        Returns:
            Diccionario con número -> SID (o None si falló)
        """
        if not recipients:
            return {}
        
        async def send_single(number: str) -> tuple[str, Optional[str]]:
            sid = await self.send_sms(number, message)
            return number, sid
        
        # Usar semáforo para limitar concurrencia
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def send_with_semaphore(number: str):
            async with semaphore:
                return await send_single(number)
        
        # Ejecutar envíos concurrentes
        tasks = [send_with_semaphore(number) for number in recipients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Procesar resultados
        sms_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Excepción en envío bulk: {result}")
                continue
            
            number, sid = result
            sms_results[number] = sid
        
        successful = len([sid for sid in sms_results.values() if sid is not None])
        logger.info(f"SMS bulk completado: {successful}/{len(recipients)} exitosos")
        
        return sms_results
    
    async def send_alert_sms(
        self,
        to_number: str,
        alert_data: Dict[str, Any],
        include_location: bool = True
    ) -> Optional[str]:
        """
        Enviar SMS de alerta con formato predefinido
        
        Args:
            to_number: Número destino
            alert_data: Datos de la alerta
            include_location: Incluir coordenadas en el mensaje
            
        Returns:
            SID del mensaje si fue exitoso
        """
        try:
            # Construir mensaje de alerta
            severidad_emoji = {
                'critica': '🚨',
                'alta': '⚠️',
                'media': '⚡',
                'baja': 'ℹ️'
            }
            
            tipo_emoji = {
                'calor_extremo': '🔥',
                'frio_extremo': '🥶',
                'cambio_brusco': '📈'
            }
            
            emoji_sev = severidad_emoji.get(alert_data.get('severidad', ''), '⚠️')
            emoji_tipo = tipo_emoji.get(alert_data.get('tipo_alerta', ''), '📊')
            
            message_parts = [
                f"{emoji_sev} ALERTA {alert_data.get('severidad', 'DESCONOCIDA').upper()}",
                f"{emoji_tipo} {alert_data.get('tipo_alerta', 'Tipo desconocido').replace('_', ' ').title()}",
                f"🌡️ Valor: {alert_data.get('valor_actual', 'N/A')}°C"
            ]
            
            # Añadir sensor si está disponible
            if alert_data.get('sensor_nombre'):
                message_parts.append(f"📡 Sensor: {alert_data['sensor_nombre']}")
            
            # Añadir ubicación si se solicita
            if include_location and alert_data.get('sensor_lat') and alert_data.get('sensor_lon'):
                lat = alert_data['sensor_lat']
                lon = alert_data['sensor_lon']
                message_parts.append(f"📍 Ubicación: {lat:.4f}, {lon:.4f}")
                message_parts.append(f"🗺️ Maps: https://maps.google.com/?q={lat},{lon}")
            
            # Añadir refugio cercano si está disponible
            if alert_data.get('refugio_nombre'):
                message_parts.append(f"🏠 Refugio: {alert_data['refugio_nombre']}")
            
            # Añadir timestamp
            if alert_data.get('fecha_deteccion'):
                fecha = alert_data['fecha_deteccion']
                if isinstance(fecha, str):
                    from datetime import datetime
                    fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                message_parts.append(f"🕐 {fecha.strftime('%d/%m/%Y %H:%M')}")
            
            message = '\n'.join(message_parts)
            
            return await self.send_sms(to_number, message, priority="high")
            
        except Exception as e:
            logger.error(f"Error enviando SMS de alerta: {e}")
            return None
    
    async def send_evacuation_sms(
        self,
        to_number: str,
        refugio_data: Dict[str, Any],
        route_info: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Enviar SMS con información de evacuación
        
        Args:
            to_number: Número destino
            refugio_data: Información del refugio
            route_info: Información de la ruta (opcional)
            
        Returns:
            SID del mensaje si fue exitoso
        """
        try:
            message_parts = [
                "🚨 AVISO DE EVACUACIÓN",
                f"🏠 Refugio: {refugio_data.get('nombre', 'Refugio de emergencia')}",
                f"📍 Dirección: {refugio_data.get('direccion', 'Ver coordenadas')}"
            ]
            
            # Añadir capacidad disponible
            if refugio_data.get('capacidad_maxima') and refugio_data.get('capacidad_actual'):
                disponible = refugio_data['capacidad_maxima'] - refugio_data['capacidad_actual']
                message_parts.append(f"👥 Capacidad: {disponible} plazas disponibles")
            
            # Añadir servicios disponibles
            servicios = []
            if refugio_data.get('tiene_aire_acondicionado'):
                servicios.append("AC")
            if refugio_data.get('tiene_calefaccion'):
                servicios.append("Calefacción")
            if refugio_data.get('tiene_servicio_medico'):
                servicios.append("Médico")
            if refugio_data.get('tiene_cocina'):
                servicios.append("Cocina")
            
            if servicios:
                message_parts.append(f"🛠️ Servicios: {', '.join(servicios)}")
            
            # Añadir coordenadas y enlace a maps
            if refugio_data.get('lat') and refugio_data.get('lon'):
                lat = refugio_data['lat']
                lon = refugio_data['lon']
                message_parts.append(f"🗺️ Coordenadas: {lat:.4f}, {lon:.4f}")
                message_parts.append(f"📱 Navegación: https://maps.google.com/dir/?api=1&destination={lat},{lon}")
            
            # Añadir información de ruta si está disponible
            if route_info:
                if route_info.get('tiempo_estimado_minutos'):
                    tiempo = route_info['tiempo_estimado_minutos']
                    message_parts.append(f"⏱️ Tiempo estimado: {tiempo} minutos")
            
            # Añadir contacto del refugio
            if refugio_data.get('telefono'):
                message_parts.append(f"📞 Contacto: {refugio_data['telefono']}")
            
            message_parts.append("⚠️ Siga las instrucciones de las autoridades")
            
            message = '\n'.join(message_parts)
            
            return await self.send_sms(to_number, message, priority="urgent")
            
        except Exception as e:
            logger.error(f"Error enviando SMS de evacuación: {e}")
            return None
    
    async def send_system_status_sms(
        self,
        to_number: str,
        status_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Enviar SMS con estado del sistema
        
        Args:
            to_number: Número destino
            status_data: Datos de estado del sistema
            
        Returns:
            SID del mensaje si fue exitoso
        """
        try:
            estado_general = status_data.get('estado_general', 'DESCONOCIDO')
            
            # Emoji según estado
            estado_emoji = {
                'NORMAL': '✅',
                'VIGILANCIA': '👁️',
                'ALERTA': '⚠️',
                'EMERGENCIA': '🚨'
            }
            
            emoji = estado_emoji.get(estado_general, '📊')
            
            message_parts = [
                f"{emoji} ESTADO DEL SISTEMA: {estado_general}",
                f"📡 Sensores activos: {status_data.get('sensores_activos', 0)}/{status_data.get('total_sensores', 0)}",
                f"🚨 Alertas activas: {status_data.get('alertas_activas', 0)}"
            ]
            
            # Añadir alertas críticas si las hay
            alertas_criticas = status_data.get('alertas_criticas', 0)
            if alertas_criticas > 0:
                message_parts.append(f"🔴 Alertas críticas: {alertas_criticas}")
            
            # Añadir estado de refugios
            refugios_disponibles = status_data.get('refugios_disponibles', 0)
            if refugios_disponibles > 0:
                message_parts.append(f"🏠 Refugios disponibles: {refugios_disponibles}")
            
            # Añadir temperatura promedio si está disponible
            temp_promedio = status_data.get('temperatura_promedio')
            if temp_promedio is not None:
                message_parts.append(f"🌡️ Temp. promedio: {temp_promedio}°C")
            
            # Añadir timestamp
            message_parts.append(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            
            message = '\n'.join(message_parts)
            
            return await self.send_sms(to_number, message, priority="normal")
            
        except Exception as e:
            logger.error(f"Error enviando SMS de estado: {e}")
            return None
    
    async def get_message_status(self, message_sid: str) -> Optional[Dict[str, Any]]:
        """
        Obtener estado de un mensaje enviado
        
        Args:
            message_sid: SID del mensaje
            
        Returns:
            Diccionario con información del mensaje
        """
        if not self.enabled or not message_sid or message_sid.startswith('sim_'):
            return {
                "sid": message_sid,
                "status": "delivered",
                "simulated": True
            }
        
        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages(message_sid).fetch()
            )
            
            return {
                "sid": message.sid,
                "status": message.status,
                "date_created": message.date_created,
                "date_sent": message.date_sent,
                "date_updated": message.date_updated,
                "direction": message.direction,
                "from": message.from_,
                "to": message.to,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "price": message.price,
                "price_unit": message.price_unit
            }
            
        except TwilioException as e:
            logger.error(f"Error obteniendo estado del mensaje {message_sid}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error general obteniendo estado del mensaje: {e}")
            return None
    
    def is_enabled(self) -> bool:
        """Verificar si el servicio Twilio está habilitado"""
        return self.enabled
    
    async def validate_phone_number(self, phone_number: str) -> bool:
        """
        Validar formato de número de teléfono
        
        Args:
            phone_number: Número a validar
            
        Returns:
            True si el formato es válido
        """
        try:
            # Validación básica de formato
            if not phone_number:
                return False
            
            # Normalizar número
            normalized = phone_number.strip().replace(' ', '').replace('-', '')
            
            # Debe empezar con + y tener al menos 10 dígitos
            if not normalized.startswith('+'):
                return False
            
            digits_only = normalized[1:]
            if not digits_only.isdigit() or len(digits_only) < 10:
                return False
            
            # Si Twilio está habilitado, usar su API de validación
            if self.enabled:
                try:
                    from twilio.rest import Client
                    loop = asyncio.get_event_loop()
                    
                    lookup_result = await loop.run_in_executor(
                        None,
                        lambda: self.client.lookups.phone_numbers(normalized).fetch()
                    )
                    
                    return lookup_result.phone_number is not None
                    
                except Exception as e:
                    logger.warning(f"Error validando número con Twilio: {e}")
                    # Fallback a validación básica
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error validando número de teléfono: {e}")
            return False