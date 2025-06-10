"""Configuración centralizada del sistema MCP RAG GIS"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class DatabaseSettings(BaseSettings):
    """Configuración de base de datos PostgreSQL"""
    
    host: str = Field(default="localhost", env="POSTGRES_HOST")
    port: int = Field(default=5432, env="POSTGRES_PORT")
    database: str = Field(default="gis_db", env="POSTGRES_DB")
    username: str = Field(default="postgres", env="POSTGRES_USER")
    password: str = Field(default="password", env="POSTGRES_PASSWORD")
    
    @property
    def url(self) -> str:
        """URL de conexión a PostgreSQL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        """URL de conexión asíncrona"""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

class OllamaSettings(BaseSettings):
    """Configuración de Ollama"""
    
    url: str = Field(default="http://localhost:11434", env="OLLAMA_URL")
    default_model: str = Field(default="llama3.2", env="DEFAULT_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", env="EMBEDDING_MODEL")
    
    # Parámetros del modelo
    temperature: float = Field(default=0.1)
    top_p: float = Field(default=0.9)
    max_tokens: int = Field(default=2048)

class APISettings(BaseSettings):
    """Configuración de la API"""
    
    host: str = Field(default="localhost", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    title: str = "Sistema MCP RAG GIS"
    version: str = "2.0.0"
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_methods: list[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_headers: list[str] = ["*"]

class PathSettings(BaseSettings):
    """Configuración de rutas del proyecto"""
    
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    
    # Directorios de datos
    documents_dir: Path = Field(default=None, env="DOCUMENTS_DIR")
    vector_db_dir: Path = Field(default=None, env="VECTOR_DB_DIR")
    maps_dir: Path = Field(default=None, env="MAPS_DIR")
    logs_dir: Path = Field(default=None, env="LOGS_DIR")
    
    def __post_init__(self):
        """Inicializar rutas si no están definidas"""
        if self.documents_dir is None:
            self.documents_dir = self.base_dir / "data" / "documents"
        if self.vector_db_dir is None:
            self.vector_db_dir = self.base_dir / "data" / "chroma_db"
        if self.maps_dir is None:
            self.maps_dir = self.base_dir / "data" / "maps"
        if self.logs_dir is None:
            self.logs_dir = self.base_dir / "logs"
        
        # Crear directorios
        for directory in [self.documents_dir, self.vector_db_dir, self.maps_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

class RAGSettings(BaseSettings):
    """Configuración del sistema RAG"""
    
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    similarity_search_k: int = Field(default=5)
    
    # Tipos de archivo soportados
    supported_extensions: list[str] = [".md", ".pdf", ".csv", ".txt", ".docx"]

class GISSettings(BaseSettings):
    """Configuración del sistema GIS"""
    
    default_crs: str = Field(default="EPSG:4326")  # WGS84
    projected_crs: str = Field(default="EPSG:3857")  # Web Mercator
    
    # Configuración de búsqueda
    default_search_radius: int = Field(default=2000)  # metros
    max_search_radius: int = Field(default=10000)  # metros
    
    # Tipos de equipamientos
    facility_types: dict = Field(default_factory=lambda: {
        'hospital': {
            'query': 'amenity=hospital',
            'icon': 'plus',
            'color': 'red',
            'name': 'Hospital',
            'priority': 1
        },
        'school': {
            'query': 'amenity=school',
            'icon': 'graduation-cap',
            'color': 'blue',
            'name': 'Colegio',
            'priority': 2
        },
        'pharmacy': {
            'query': 'amenity=pharmacy',
            'icon': 'medkit',
            'color': 'green',
            'name': 'Farmacia',
            'priority': 3
        },
        'police': {
            'query': 'amenity=police',
            'icon': 'shield',
            'color': 'darkblue',
            'name': 'Comisaría',
            'priority': 4
        },
        'fire_station': {
            'query': 'amenity=fire_station',
            'icon': 'fire',
            'color': 'orange',
            'name': 'Bomberos',
            'priority': 5
        },
        'library': {
            'query': 'amenity=library',
            'icon': 'book',
            'color': 'purple',
            'name': 'Biblioteca',
            'priority': 6
        },
        'post_office': {
            'query': 'amenity=post_office',
            'icon': 'envelope',
            'color': 'yellow',
            'name': 'Correos',
            'priority': 7
        },
        'bank': {
            'query': 'amenity=bank',
            'icon': 'university',
            'color': 'darkgreen',
            'name': 'Banco',
            'priority': 8
        }
    })

class LoggingSettings(BaseSettings):
    """Configuración de logging"""
    
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Archivos de log
    main_log_file: str = "main.log"
    error_log_file: str = "errors.log"
    access_log_file: str = "access.log"

class Settings(BaseSettings):
    """Configuración principal del sistema"""
    
    # Configuraciones específicas
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    api: APISettings = Field(default_factory=APISettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    gis: GISSettings = Field(default_factory=GISSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Instancia global de configuración
settings = Settings()