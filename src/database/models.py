"""Modelos de datos para PostgreSQL"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid
from datetime import datetime

Base = declarative_base()

class SeccionCensal(Base):
    """Modelo para secciones censales"""
    
    __tablename__ = 'secciones_censales'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_seccion = Column(String(20), nullable=False, unique=True, index=True)
    codigo_distrito = Column(String(10), nullable=False)
    codigo_municipio = Column(String(10), nullable=False)
    nombre_municipio = Column(String(100), nullable=False)
    poblacion = Column(Integer, default=0)
    superficie_km2 = Column(Float, default=0.0)
    densidad_hab_km2 = Column(Float, default=0.0)
    geom = Column(Geometry('POLYGON', srid=4326), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Equipamiento(Base):
    """Modelo para equipamientos públicos"""
    
    __tablename__ = 'equipamientos'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(200), nullable=False)
    tipo = Column(String(50), nullable=False, index=True)
    direccion = Column(String(300))
    telefono = Column(String(20))
    website = Column(String(200))
    horario_apertura = Column(String(100))
    capacidad = Column(Integer)
    publico = Column(Boolean, default=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Sensor(Base):
    """Modelo para sensores IoT"""
    
    __tablename__ = 'sensors'
    
    sensor_id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    sensor_type = Column(String(50), nullable=False, index=True)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey('equipamientos.id'))
    location = Column(Geometry('POINT', srid=4326), nullable=False)
    active = Column(Boolean, default=True)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SensorReading(Base):
    """Modelo para lecturas de sensores (TimescaleDB hypertable)"""
    
    __tablename__ = 'sensor_readings'
    
    id = Column(Integer, primary_key=True)
    sensor_id = Column(String(50), ForeignKey('sensors.sensor_id'), nullable=False)
    reading_type = Column(String(50), nullable=False, index=True)
    value = Column(Numeric, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    metadata = Column(JSON, default={})

class SensorAlert(Base):
    """Modelo para alertas de sensores"""
    
    __tablename__ = 'sensor_alerts'
    
    id = Column(Integer, primary_key=True)
    sensor_id = Column(String(50), ForeignKey('sensors.sensor_id'), nullable=False)
    reading_type = Column(String(50), nullable=False)
    value = Column(Numeric, nullable=False)
    level = Column(String(20), nullable=False)  # CRITICAL, WARNING, INFO
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))