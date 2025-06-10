"""Módulo de base de datos"""

from .postgres_client import PostgreSQLClient, postgres_client
from .models import Base, SeccionCensal, Equipamiento

__all__ = [
    "PostgreSQLClient",
    "postgres_client", 
    "Base",
    "SeccionCensal",
    "Equipamiento"
]