"""Utilidades para envío de alertas SMS via Twilio"""

import logging
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import settings

logger = logging.getLogger(__name__)

class TwilioNotifier:
    """Servicio de notificaciones SMS con Twilio"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Inicializar cliente Twilio si está configurado"""
        if settings.twilio.is_configured:
            try:
                self.client = Client(
                    settings.twilio.account_sid,
                    settings.twilio.auth_token
                )
                logger.info("Cliente Twilio inicializado correctamente")
            except Exception as e:
                logger.error(f"Error inicializando Twilio: {e}")
        else:
            logger.warning("Twilio no configurado - alertas SMS deshabilitadas")
    
    def send_sms(self, to_number: str, message: str) -> Optional[str]:
        """
        Enviar SMS de alerta
        
        Args:
            to_number: Número de destino (formato internacional)
            message: Mensaje a enviar
            
        Returns:
            SID del mensaje si es exitoso, None si falla
        """
        if not self.client:
            logger.warning("Cliente Twilio no disponible")
            return None
        
        try:
            message = self.client.messages.create(
                body=message,
                from_=settings.twilio.from_number,
                to=to_number
            )
            
            logger.info(f"SMS enviado exitosamente: {message.sid}")
            return message.sid
            
        except TwilioException as e:
            logger.error(f"Error enviando SMS: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado enviando SMS: {e}")
            return None
    
    def send_alert(self, sensor_id: str, alert_level: str, 
                   value: float, threshold: float, 
                   recipient: str) -> bool:
        """
        Enviar alerta de sensor formateada
        
        Args:
            sensor_id: ID del sensor
            alert_level: Nivel de alerta (CRITICAL, WARNING)
            value: Valor actual
            threshold: Umbral superado
            recipient: Número de teléfono destino
            
        Returns:
            True si el envío fue exitoso
        """
        emoji = "🚨" if alert_level == "CRITICAL" else "⚠️"
        
        message = f"{emoji} ALERTA {alert_level}\n"
        message += f"Sensor: {sensor_id}\n"
        message += f"Valor: {value}\n"
        message += f"Umbral: {threshold}\n"
        message += f"Hora: {datetime.now().strftime('%H:%M')}"
        
        return self.send_sms(recipient, message) is not None

# Instancia global
twilio_notifier = TwilioNotifier()