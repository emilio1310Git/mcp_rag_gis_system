"""API REST principal con FastAPI"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from ..config import settings
from ..database import postgres_client
from .routers import maps, gis, timeseries

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.logging.level),
    format=settings.logging.format
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # Startup
    logger.info("🚀 Iniciando API...")
    try:
        await postgres_client.initialize()
        logger.info("✅ Base de datos inicializada")
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Cerrando API...")
    try:
        await postgres_client.close()
        logger.info("✅ Base de datos cerrada")
    except Exception as e:
        logger.error(f"❌ Error cerrando base de datos: {e}")

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.api.title,
    version=settings.api.version,
    debug=settings.api.debug,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=settings.api.cors_methods,
    allow_headers=settings.api.cors_headers,
)

# Montar archivos estáticos para mapas
app.mount("/static", StaticFiles(directory=str(settings.paths.maps_dir)), name="static")

# Incluir routers
app.include_router(maps.router, prefix="/api/maps", tags=["maps"])
app.include_router(gis.router, prefix="/api/gis", tags=["gis"])
app.include_router(timeseries.router, prefix="/api/timeseries", tags=["timeseries"])

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": f"Sistema MCP RAG GIS + TimescaleDB v{settings.api.version}",
        "status": "running",
        "endpoints": {
            "maps": "/api/maps",
            "gis": "/api/gis",
            "timeseries": "/api/timeseries",  
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint de salud"""
    try:
        # Verificar conexión a base de datos
        result = await postgres_client.execute_query("SELECT 1 as health")
        db_status = "ok" if result else "error"
    except Exception:
        db_status = "error"
    
    return {
        "status": "ok",
        "database": db_status,
        "version": settings.api.version
    }

@app.get("/map/{map_filename}")
async def serve_map(map_filename: str):
    """Servir archivos de mapas HTML"""
    map_path = settings.paths.maps_dir / map_filename
    
    if map_path.exists() and map_path.suffix == '.html':
        return FileResponse(str(map_path), media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Mapa no encontrado")

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug
    )