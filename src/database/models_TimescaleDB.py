"""
Modelos de datos para TimescaleDB - Versión ampliada
Implementa las tablas de sensores, observaciones y agregados continuos
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid
from datetime import datetime

Base = declarative_base()

class Sensor(Base):
    """Modelo para sensores IoT/ambientales"""
    
    __tablename__ = 'sensores'
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False)
    tipo_sensor = Column(String(50), nullable=False)  # temperatura, humedad, calidad_aire, etc.
    estado = Column(String(20), default='activo')  # activo, inactivo, mantenimiento
    fecha_instalacion = Column(DateTime, default=datetime.utcnow)
    localizacion = Column(Geometry('POINT', srid=4326), nullable=False)
    
    # Metadatos del sensor
    fabricante = Column(String(100))
    modelo = Column(String(100))
    numero_serie = Column(String(100))
    precision_medicion = Column(Float)  # ±0.1°C, ±2%, etc.
    rango_min = Column(Float)
    rango_max = Column(Float)
    unidad_medida = Column(String(20))  # °C, %, ppm, etc.
    
    # Conectividad
    protocolo_comunicacion = Column(String(50))  # LoRaWAN, WiFi, 4G, etc.
    frecuencia_envio = Column(Integer)  # segundos entre mediciones
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Observacion(Base):
    """Modelo para observaciones de sensores - Hypertable TimescaleDB"""
    
    __tablename__ = 'observaciones'
    
    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey('sensores.id'), nullable=False)
    
    # Datos de la medición
    valor = Column(Float, nullable=False)
    unidad = Column(String(20))
    calidad_dato = Column(String(20), default='buena')  # buena, regular, mala, dudosa
    
    # Timestamp (columna de particionado TimescaleDB)
    fecha_observacion = Column(DateTime, nullable=False)
    
    # Localización (puede variar para sensores móviles)
    localizacion = Column(Geometry('POINT', srid=4326))
    
    # Metadatos adicionales
    temperatura_ambiente = Column(Float)  # para contexto
    humedad_ambiente = Column(Float)
    presion_atmosferica = Column(Float)
    velocidad_viento = Column(Float)
    direccion_viento = Column(Float)
    
    # Información del dispositivo
    nivel_bateria = Column(Float)  # %
    intensidad_senal = Column(Float)  # dBm o %
    
    # Procesamiento
    valor_procesado = Column(Float)  # valor después de calibración/filtros
    algoritmo_procesamiento = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)

class RefugioEmergencia(Base):
    """Modelo para refugios de emergencia"""
    
    __tablename__ = 'refugios'
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False)
    tipo_refugio = Column(String(50), nullable=False)  # temporal, permanente, especializado
    
    # Ubicación
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    direccion = Column(String(300))
    municipio = Column(String(100))
    provincia = Column(String(100))
    
    # Capacidad y recursos
    capacidad_maxima = Column(Integer)
    capacidad_actual = Column(Integer, default=0)
    estado_operativo = Column(String(20), default='disponible')  # disponible, lleno, cerrado, mantenimiento
    
    # Servicios disponibles
    tiene_agua_potable = Column(Boolean, default=True)
    tiene_electricidad = Column(Boolean, default=True)
    tiene_calefaccion = Column(Boolean, default=False)
    tiene_aire_acondicionado = Column(Boolean, default=False)
    tiene_servicio_medico = Column(Boolean, default=False)
    tiene_cocina = Column(Boolean, default=False)
    
    # Accesibilidad
    accesible_discapacitados = Column(Boolean, default=False)
    acceso_vehicular = Column(Boolean, default=True)
    
    # Información de contacto
    telefono = Column(String(20))
    email = Column(String(100))
    responsable = Column(String(200))
    
    # Alertas y umbrales
    umbral_temperatura_max = Column(Float, default=40.0)  # °C
    umbral_temperatura_min = Column(Float, default=-5.0)  # °C
    umbral_calidad_aire = Column(Float, default=150.0)    # AQI
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RedViaria(Base):
    """Modelo para red viaria para rutas con pgRouting"""
    
    __tablename__ = 'edges'
    
    id = Column(Integer, primary_key=True)
    source = Column(Integer, nullable=False)
    target = Column(Integer, nullable=False)
    
    # Costos para routing
    cost = Column(Float, nullable=False)  # tiempo en minutos
    reverse_cost = Column(Float)  # para calles de una dirección
    
    # Información de la vía
    nombre_via = Column(String(200))
    tipo_via = Column(String(50))  # autopista, nacional, local, sendero
    estado_via = Column(String(20), default='transitable')  # transitable, cortada, obras
    
    # Restricciones
    permitido_vehiculos = Column(Boolean, default=True)
    permitido_peatones = Column(Boolean, default=True)
    permitido_bicicletas = Column(Boolean, default=True)
    
    # Características físicas
    ancho_metros = Column(Float)
    pendiente_porcentaje = Column(Float)
    superficie = Column(String(50))  # asfalto, tierra, grava
    
    # Geometría
    geom = Column(Geometry('LINESTRING', srid=4326), nullable=False)
    longitud_metros = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NodosRed(Base):
    """Modelo para nodos de la red viaria"""
    
    __tablename__ = 'nodes'
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(200))
    tipo_nodo = Column(String(50))  # cruce, rotonda, salida, entrada
    
    # Geometría
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

# Agregados continuos - Se definen vía SQL en TimescaleDB
class TempHoraria(Base):
    """Vista materializada para agregados horarios de temperatura"""
    
    __tablename__ = 'temp_horaria'
    
    hora = Column(DateTime, primary_key=True)
    sensor_id = Column(Integer, primary_key=True)
    temp_media = Column(Float)
    temp_min = Column(Float)
    temp_max = Column(Float)
    num_observaciones = Column(Integer)
    desviacion_estandar = Column(Float)

class TempDiaria(Base):
    """Vista materializada para agregados diarios de temperatura"""
    
    __tablename__ = 'temp_diaria'
    
    dia = Column(DateTime, primary_key=True)
    sensor_id = Column(Integer, primary_key=True)
    temp_media = Column(Float)
    temp_min = Column(Float)
    temp_max = Column(Float)
    temp_min_hora = Column(DateTime)
    temp_max_hora = Column(DateTime)
    horas_por_encima_umbral = Column(Integer)
    calidad_datos_porcentaje = Column(Float)

class AlertaTemperatura(Base):
    """Modelo para alertas de temperatura"""
    
    __tablename__ = 'alertas_temperatura'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_id = Column(Integer, ForeignKey('sensores.id'), nullable=False)
    refugio_id = Column(Integer, ForeignKey('refugios.id'))
    
    # Tipo de alerta
    tipo_alerta = Column(String(50), nullable=False)  # calor_extremo, frio_extremo, cambio_brusco
    severidad = Column(String(20), nullable=False)   # baja, media, alta, critica
    
    # Valores que dispararon la alerta
    valor_actual = Column(Float, nullable=False)
    umbral_configurado = Column(Float, nullable=False)
    duracion_minutos = Column(Integer)
    
    # Estado de la alerta
    estado = Column(String(20), default='activa')  # activa, reconocida, resuelta
    fecha_deteccion = Column(DateTime, nullable=False)
    fecha_reconocimiento = Column(DateTime)
    fecha_resolucion = Column(DateTime)
    
    # Respuesta automática
    sms_enviado = Column(Boolean, default=False)
    email_enviado = Column(Boolean, default=False)
    refugio_notificado = Column(Boolean, default=False)
    
    # Información adicional
    mensaje_alerta = Column(Text)
    acciones_recomendadas = Column(Text)
    personal_notificado = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)