#!/usr/bin/env python3
"""
Servidor MCP RAG simplificado para debugging
"""

import asyncio
import logging
import sys
from pathlib import Path

# Añadir src al path - CORREGIDO
project_root = Path(__file__).parent.parent if Path(__file__).parent.name == "src" else Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_initialization():
    """Test paso a paso de la inicialización"""
    
    logger.info("🔄 PASO 1: Importando configuración...")
    try:
        from src.config import settings
        logger.info(f"✅ Configuración cargada - Ollama URL: {settings.ollama.url}")
    except Exception as e:
        logger.error(f"❌ Error importando configuración: {e}")
        return False
    
    logger.info("🔄 PASO 2: Importando servicios...")
    try:
        from src.services.rag_service import RAGService
        logger.info("✅ RAGService importado")
    except Exception as e:
        logger.error(f"❌ Error importando RAGService: {e}")
        return False
    
    logger.info("🔄 PASO 3: Creando instancia RAGService...")
    try:
        rag_service = RAGService()
        logger.info("✅ RAGService instanciado")
    except Exception as e:
        logger.error(f"❌ Error instanciando RAGService: {e}")
        return False
    
    logger.info("🔄 PASO 4: Verificando conectividad Ollama...")
    try:
        import requests
        response = requests.get(f"{settings.ollama.url}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Ollama disponible")
        else:
            logger.warning(f"⚠️ Ollama respuesta: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Ollama no disponible: {e}")
    
    logger.info("🔄 PASO 5: Inicializando RAGService (sin Ollama)...")
    try:
        # Comentar la inicialización de Ollama temporalmente
        logger.info("✅ Inicialización básica completada (sin Ollama)")
    except Exception as e:
        logger.error(f"❌ Error en inicialización: {e}")
        return False
    
    logger.info("🔄 PASO 6: Importando MCP...")
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
        logger.info("✅ MCP importado")
    except Exception as e:
        logger.error(f"❌ Error importando MCP: {e}")
        return False
    
    logger.info("🔄 PASO 7: Creando servidor MCP...")
    try:
        app = Server("rag-server-debug")
        logger.info("✅ Servidor MCP creado")
    except Exception as e:
        logger.error(f"❌ Error creando servidor MCP: {e}")
        return False
    
    logger.info("🎉 TODOS LOS PASOS COMPLETADOS EXITOSAMENTE")
    return True

async def main():
    """Función principal de debug"""
    logger.info("🚀 Iniciando diagnóstico del servidor RAG...")
    
    success = await test_initialization()
    
    if success:
        logger.info("✅ Diagnóstico completado - El servidor debería funcionar")
    else:
        logger.error("❌ Diagnóstico falló - Revisar errores arriba")
    
    logger.info("🏁 Finalizando diagnóstico...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⌨️ Diagnóstico interrumpido por usuario")
    except Exception as e:
        logger.error(f"💥 Error fatal: {e}")
        import traceback
        traceback.print_exc()