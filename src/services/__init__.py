"""Módulo de servicios"""

# from .rag_service import RAGService
# from .maps_service import MapsService
# from .gis_service import GISService

# Evitar importaciones circulares - importar solo cuando sea necesario
__all__ = ["RAGService", "MapsService", "GISService"]

def __getattr__(name):
    if name == "RAGService":
        from .rag_service import RAGService
        return RAGService
    elif name == "MapsService":
        from .maps_service import MapsService
        return MapsService
    elif name == "GISService":
        from .gis_service import GISService
        return GISService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")