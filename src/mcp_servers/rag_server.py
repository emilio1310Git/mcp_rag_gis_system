"""Servidor MCP para RAG actualizado"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Configurar path para importaciones
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Importaciones del proyecto (ahora absolutas)
from services.rag_service import RAGService
from config import settings

# Importaciones MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Inicializar servicio RAG
rag_service = RAGService()

# Crear servidor MCP
app = Server("rag-server-v2")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Listar herramientas RAG disponibles"""
    return [
        Tool(
            name="initialize_rag",
            description="Inicializar sistema RAG con Ollama",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="process_documents",
            description="Procesar documentos (MD, PDF, CSV, TXT) y crear base de datos vectorial",
            inputSchema={
                "type": "object",
                "properties": {
                    "documents_path": {
                        "type": "string",
                        "description": "Ruta al directorio con documentos"
                    },
                    "recreate_vectorstore": {
                        "type": "boolean",
                        "description": "Recrear vectorstore desde cero",
                        "default": False
                    }
                },
                "required": ["documents_path"]
            }
        ),
        Tool(
            name="query_documents",
            description="Realizar consulta RAG sobre los documentos procesados",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Pregunta sobre los documentos"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="list_documents",
            description="Listar documentos disponibles en un directorio",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Ruta del directorio",
                        "default": str(settings.paths.documents_dir)
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_vectorstore_info",
            description="Obtener información del vectorstore actual",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Ejecutar herramientas RAG"""
    
    try:
        if name == "initialize_rag":
            await rag_service.initialize()
            return [TextContent(
                type="text",
                text="✅ Sistema RAG inicializado correctamente con LangChain 0.3+ y Ollama"
            )]
        
        elif name == "process_documents":
            documents_path = arguments.get("documents_path")
            recreate = arguments.get("recreate_vectorstore", False)
            
            # Procesar documentos
            documents = await rag_service.process_documents(documents_path)
            
            if documents:
                if recreate or not rag_service.vectorstore:
                    # Crear nuevo vectorstore
                    success = await rag_service.create_vectorstore(documents)
                else:
                    # Añadir a vectorstore existente
                    success = await rag_service.add_documents(documents)
                
                if success:
                    result = f"✅ Procesados {len(documents)} chunks de documentos.\n"
                    result += f"📍 Base de datos vectorial {'creada' if recreate else 'actualizada'} en: {settings.paths.vector_db_dir}"
                else:
                    result = "❌ Error procesando documentos."
            else:
                result = "⚠️ No se encontraron documentos para procesar."
            
            return [TextContent(type="text", text=result)]
        
        elif name == "query_documents":
            question = arguments.get("question")
            
            if not rag_service.retrieval_chain:
                await rag_service.initialize()
            
            result = await rag_service.query(question)
            
            if "error" in result:
                return [TextContent(type="text", text=f"❌ {result['error']}")]
            
            response = f"**Respuesta:**\n{result['answer']}\n\n"
            response += f"**Fuentes consultadas ({result['num_sources']}):**\n"
            
            for i, source in enumerate(result['sources'], 1):
                response += f"{i}. {source['file_name']} (chunk {source['chunk_id']})\n"
                response += f"   📄 {source['content_preview']}\n\n"
            
            return [TextContent(type="text", text=response)]
        
        elif name == "list_documents":
            path = arguments.get("path", str(settings.paths.documents_dir))
            documents = await rag_service.list_documents(path)
            
            if documents:
                result = f"📁 Documentos en {path}:\n\n"
                for doc in documents:
                    size_mb = doc['size'] / (1024 * 1024)
                    result += f"📄 **{doc['name']}**\n"
                    result += f"   Tamaño: {size_mb:.2f} MB\n"
                    result += f"   Tipo: {doc['extension']}\n\n"
            else:
                result = f"📂 No se encontraron documentos compatibles en {path}"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_vectorstore_info":
            info = await rag_service.get_vectorstore_info()
            
            result = "📊 **Información del Vectorstore:**\n\n"
            result += f"Estado: {info['status']}\n"
            result += f"Documentos: {info.get('document_count', 0)}\n"
            result += f"Modelo embeddings: {info.get('embedding_model', 'N/A')}\n"
            result += f"Modelo LLM: {info.get('llm_model', 'N/A')}\n"
            
            if 'error' in info:
                result += f"Error: {info['error']}\n"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"❌ Herramienta desconocida: {name}")]
    
    except Exception as e:
        logger.error(f"Error en herramienta {name}: {e}")
        return [TextContent(type="text", text=f"❌ Error ejecutando {name}: {str(e)}")]

async def main():
    """Función principal del servidor RAG"""
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())