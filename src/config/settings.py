"""Configuración centralizada del sistema MCP RAG GIS + TimescaleDB"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class DatabaseSettings(BaseSettings):
    """Configuración de base de datos PostgreSQL + TimescaleDB"""
    
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="Host de PostgreSQL")
    port: int = Field(default=5432, description="Puerto de PostgreSQL")
    db: str = Field(default="gis_db", description="Nombre de la base de datos")
    user: str = Field(default="postgres", description="Usuario de PostgreSQL")
    password: str = Field(default="password", description="Contraseña de PostgreSQL")
    
    # Configuración específica de TimescaleDB
    enable_timescale: bool = Field(default=True, description="Habilitar extensión TimescaleDB")
    chunk_time_interval: str = Field(default="7 days", description="Intervalo de chunks para hypertables")
    
    @property
    def url(self) -> str:
        """URL de conexión a PostgreSQL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
    
    @property
    def async_url(self) -> str:
        """URL de conexión asíncrona"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
    
    # Propiedades de compatibilidad
    @property
    def database(self) -> str:
        return self.db
    
    @property
    def username(self) -> str:
        return self.user

class OllamaSettings(BaseSettings):
    """Configuración de Ollama"""
    
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        case_sensitive=False,
        extra="ignore"
    )
    
    url: str = Field(default="http://localhost:11434", description="URL de Ollama")
    
    # Modelos (sin prefijo para compatibilidad)
    default_model: str = Field(default="llama3.2")
    embedding_model: str = Field(default="nomic-embed-text")
    
    # Parámetros del modelo
    temperature: float = Field(default=0.1)
    top_p: float = Field(default=0.9)
    max_tokens: int = Field(default=2048)
    
    def __init__(self, **kwargs):
        # Manejar variables de entorno sin prefijo para modelos
        env_default_model = os.getenv("DEFAULT_MODEL")
        env_embedding_model = os.getenv("EMBEDDING_MODEL")
        
        if env_default_model and "default_model" not in kwargs:
            kwargs["default_model"] = env_default_model
        if env_embedding_model and "embedding_model" not in kwargs:
            kwargs["embedding_model"] = env_embedding_model
            
        super().__init__(**kwargs)

class APISettings(BaseSettings):
    """Configuración de la API"""
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="Host de la API")
    port: int = Field(default=8000, description="Puerto de la API")
    debug: bool = Field(default=False, description="Modo debug")
    title: str = Field(default="Sistema MCP RAG GIS + TimescaleDB")
    version: str = Field(default="2.1.0")
    
    # CORS
    cors_origins: List[str] = Field(default=[
        "http://localhost:3000", 
        "http://localhost:8080", 
        "http://localhost:8050"
    ])
    cors_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_headers: List[str] = Field(default=["*"])
    
    def __init__(self, **kwargs):
        # Manejar DEBUG sin prefijo para compatibilidad
        env_debug = os.getenv("DEBUG")
        if env_debug and "debug" not in kwargs:
            kwargs["debug"] = env_debug.lower() in ("true", "1", "yes", "on")
            
        super().__init__(**kwargs)

class DashboardSettings(BaseSettings):
    """Configuración del dashboard Dash"""
    
    model_config = SettingsConfigDict(
        env_prefix="DASH_",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="Host del dashboard")
    port: int = Field(default=8050, description="Puerto del dashboard")
    debug: bool = Field(default=True, description="Modo debug de Dash")
    update_interval: int = Field(default=5000, description="Intervalo de actualización en ms")

class TwilioSettings(BaseSettings):
    """Configuración de Twilio para alertas SMS"""
    
    model_config = SettingsConfigDict(
        env_prefix="TWILIO_",
        case_sensitive=False,
        extra="ignore"
    )
    
    account_sid: Optional[str] = Field(default=None, description="Twilio Account SID")
    auth_token: Optional[str] = Field(default=None, description="Twilio Auth Token")
    from_number: Optional[str] = Field(default=None, description="Número Twilio origen")
    
    @property
    def is_configured(self) -> bool:
        """Verificar si Twilio está configurado"""
        return all([self.account_sid, self.auth_token, self.from_number])

class SensorSettings(BaseSettings):
    """Configuración de sensores IoT"""
    
    model_config = SettingsConfigDict(
        env_prefix="SENSOR_",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Configuración de simulación de datos
    simulation_enabled: bool = Field(default=True, description="Habilitar simulación de sensores")
    simulation_interval: int = Field(default=30, description="Intervalo de simulación en segundos")
    
    # Tipos de sensores soportados
    supported_types: List[str] = Field(default=[
        "temperature", "humidity", "air_quality", "noise", "occupancy"
    ])
    
    # Límites de alerta por defecto
    default_thresholds: Dict[str, Dict[str, float]] = Field(default_factory=lambda: {
        "temperature": {"min": -10, "max": 45, "critical": 50},
        "humidity": {"min": 10, "max": 90, "critical": 95},
        "air_quality": {"min": 0, "max": 150, "critical": 300},
        "noise": {"min": 0, "max": 70, "critical": 85},
        "occupancy": {"min": 0, "max": 100, "critical": 120}
    })

class PathSettings(BaseSettings):
    """Configuración de rutas del proyecto"""
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )
    
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    
    # Directorios de datos existentes
    documents_dir: Optional[Path] = Field(default=None)
    vector_db_dir: Optional[Path] = Field(default=None)
    maps_dir: Optional[Path] = Field(default=None)
    logs_dir: Optional[Path] = Field(default=None)
    
    # Nuevos directorios para TimescaleDB
    sensor_data_dir: Optional[Path] = Field(default=None)
    dashboard_static_dir: Optional[Path] = Field(default=None)
    
    def __init__(self, **kwargs):
        # Manejar variables de entorno de directorios
        env_mappings = {
            "documents_dir": "DOCUMENTS_DIR",
            "vector_db_dir": "VECTOR_DB_DIR", 
            "maps_dir": "MAPS_DIR",
            "logs_dir": "LOGS_DIR",
            "sensor_data_dir": "SENSOR_DATA_DIR",
            "dashboard_static_dir": "DASHBOARD_STATIC_DIR"
        }
        
        for field_name, env_var in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value and field_name not in kwargs:
                kwargs[field_name] = Path(env_value)
        
        super().__init__(**kwargs)
        
        # Crear directorios por defecto si no se especificaron
        if self.documents_dir is None:
            self.documents_dir = self.base_dir / "data" / "documents"
        if self.vector_db_dir is None:
            self.vector_db_dir = self.base_dir / "data" / "chroma_db"
        if self.maps_dir is None:
            self.maps_dir = self.base_dir / "data" / "maps"
        if self.logs_dir is None:
            self.logs_dir = self.base_dir / "logs"
        if self.sensor_data_dir is None:
            self.sensor_data_dir = self.base_dir / "data" / "sensors"
        if self.dashboard_static_dir is None:
            self.dashboard_static_dir = self.base_dir / "frontend" / "static"
            
        # Crear todos los directorios
        for directory in [
            self.documents_dir, self.vector_db_dir, self.maps_dir, 
            self.logs_dir, self.sensor_data_dir, self.dashboard_static_dir
        ]:
            if directory:
                directory.mkdir(parents=True, exist_ok=True)

class RAGSettings(BaseSettings):
    """Configuración del sistema RAG"""
    
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        case_sensitive=False,
        extra="ignore"
    )
    
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    similarity_search_k: int = Field(default=5)
    
    # Tipos de archivo soportados
    supported_extensions: List[str] = Field(default=[".md", ".pdf", ".csv", ".txt", ".docx"])

class GISSettings(BaseSettings):
    """Configuración del sistema GIS"""
    
    model_config = SettingsConfigDict(
        env_prefix="GIS_",
        case_sensitive=False,
        extra="ignore"
    )
    
    default_crs: str = Field(default="EPSG:4326")  # WGS84
    projected_crs: str = Field(default="EPSG:3857")  # Web Mercator
    
    # Configuración de búsqueda
    default_search_radius: int = Field(default=2000)  # metros
    max_search_radius: int = Field(default=10000)  # metros
    
    # Tipos de equipamientos (extendido con sensores)
    facility_types: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        'hospital': {
            'query': 'amenity=hospital',
            'icon': 'plus',
            'color': 'red',
            'name': 'Hospital',
            'priority': 1,
            'can_have_sensors': True
        },
        'school': {
            'query': 'amenity=school',
            'icon': 'graduation-cap',
            'color': 'blue',
            'name': 'Colegio',
            'priority': 2,
            'can_have_sensors': True
        },
        'pharmacy': {
            'query': 'amenity=pharmacy',
            'icon': 'medkit',
            'color': 'green',
            'name': 'Farmacia',
            'priority': 3,
            'can_have_sensors': False
        },
        'police': {
            'query': 'amenity=police',
            'icon': 'shield',
            'color': 'darkblue',
            'name': 'Comisaría',
            'priority': 4,
            'can_have_sensors': True
        },
        'fire_station': {
            'query': 'amenity=fire_station',
            'icon': 'fire',
            'color': 'orange',
            'name': 'Bomberos',
            'priority': 5,
            'can_have_sensors': True
        },
        'library': {
            'query': 'amenity=library',
            'icon': 'book',
            'color': 'purple',
            'name': 'Biblioteca',
            'priority': 6,
            'can_have_sensors': True
        },
        'post_office': {
            'query': 'amenity=post_office',
            'icon': 'envelope',
            'color': 'yellow',
            'name': 'Correos',
            'priority': 7,
            'can_have_sensors': False
        },
        'bank': {
            'query': 'amenity=bank',
            'icon': 'university',
            'color': 'darkgreen',
            'name': 'Banco',
            'priority': 8,
            'can_have_sensors': False
        }
    })

class LoggingSettings(BaseSettings):
    """Configuración de logging"""
    
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        case_sensitive=False,
        extra="ignore"
    )
    
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Archivos de log
    main_log_file: str = Field(default="main.log")
    error_log_file: str = Field(default="errors.log")
    access_log_file: str = Field(default="access.log")
    sensor_log_file: str = Field(default="sensors.log")  # Nuevo
    alerts_log_file: str = Field(default="alerts.log")  # Nuevo

class Settings(BaseSettings):
    """Configuración principal del sistema"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignorar variables extra en lugar de fallar
    )
    
    # Configuraciones específicas
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    api: APISettings = Field(default_factory=APISettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)  # Nuevo
    twilio: TwilioSettings = Field(default_factory=TwilioSettings)  # Nuevo
    sensors: SensorSettings = Field(default_factory=SensorSettings)  # Nuevo
    paths: PathSettings = Field(default_factory=PathSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    gis: GISSettings = Field(default_factory=GISSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

# Instancia global de configuración
settings = Settings()