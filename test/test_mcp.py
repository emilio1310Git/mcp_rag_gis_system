#!/usr/bin/env python3
"""
Cliente de prueba para los servidores MCP
Permite probar individualmente cada servidor y sus herramientas
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

# Añadir src al path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

class MCPTester:
    """Cliente de prueba para servidores MCP"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
    
    async def test_server(self, server_module: str, tool_name: str, arguments: Dict[str, Any] = None):
        """
        Probar un servidor MCP específico
        
        Args:
            server_module: Módulo del servidor (ej: "src.mcp_servers.rag_server")
            tool_name: Nombre de la herramienta a probar
            arguments: Argumentos para la herramienta
        """
        if arguments is None:
            arguments = {}
        
        print(f"🧪 Probando {server_module} -> {tool_name}")
        print(f"📝 Argumentos: {arguments}")
        print("-" * 50)
        
        try:
            # Crear proceso del servidor
            process = subprocess.Popen(
                [sys.executable, "-m", server_module],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root)
            )
            
            # Mensaje de inicialización MCP
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            # Enviar inicialización
            process.stdin.write(json.dumps(init_message) + "\n")
            process.stdin.flush()
            
            # Leer respuesta de inicialización
            init_response = process.stdout.readline()
            print(f"✅ Inicialización: {init_response.strip()}")
            
            # Mensaje de lista de herramientas
            list_tools_message = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            # Enviar lista de herramientas
            process.stdin.write(json.dumps(list_tools_message) + "\n")
            process.stdin.flush()
            
            # Leer respuesta de herramientas
            tools_response = process.stdout.readline()
            print(f"🔧 Herramientas disponibles: {tools_response.strip()}")
            
            # Mensaje de llamada a herramienta
            call_tool_message = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # Enviar llamada a herramienta
            process.stdin.write(json.dumps(call_tool_message) + "\n")
            process.stdin.flush()
            
            # Leer respuesta de herramienta
            tool_response = process.stdout.readline()
            print(f"🎯 Respuesta de herramienta:")
            
            try:
                response_data = json.loads(tool_response)
                if "result" in response_data:
                    content = response_data["result"]["content"]
                    for item in content:
                        if item["type"] == "text":
                            print(item["text"])
                else:
                    print(f"Error: {response_data}")
            except json.JSONDecodeError:
                print(f"Respuesta cruda: {tool_response}")
            
            # Cerrar proceso
            process.stdin.close()
            process.terminate()
            
        except Exception as e:
            print(f"❌ Error en prueba: {e}")
            if process:
                process.terminate()

async def main():
    """Ejecutar pruebas de los servidores MCP"""
    tester = MCPTester()
    
    print("🚀 CLIENTE DE PRUEBA MCP RAG GIS v2.0")
    print("=" * 50)
    
    # Test 1: RAG Server - Información del vectorstore
    print("\n🧪 TEST 1: Servidor RAG - Información del vectorstore")
    await tester.test_server(
        "src.mcp_servers.rag_server",
        "get_vectorstore_info"
    )
    
    # Test 2: RAG Server - Listar documentos
    print("\n🧪 TEST 2: Servidor RAG - Listar documentos")
    await tester.test_server(
        "src.mcp_servers.rag_server", 
        "list_documents",
        {"path": "data/documents"}
    )
    
    # Test 3: Maps Server - Geocodificación
    print("\n🧪 TEST 3: Servidor Maps - Geocodificación")
    await tester.test_server(
        "src.mcp_servers.maps_server",
        "geocode_address",
        {"address": "Madrid, España"}
    )
    
    # Test 4: Maps Server - Buscar equipamientos
    print("\n🧪 TEST 4: Servidor Maps - Buscar equipamientos")
    await tester.test_server(
        "src.mcp_servers.maps_server",
        "find_nearby_facilities",
        {
            "address": "Plaza Mayor, Madrid",
            "radius": 1000,
            "facility_types": ["hospital", "pharmacy"]
        }
    )
    
    # Test 5: GIS Server - Inicialización
    print("\n🧪 TEST 5: Servidor GIS - Inicialización")
    await tester.test_server(
        "src.mcp_servers.gis_server",
        "initialize_gis"
    )
    
    print("\n🎉 PRUEBAS COMPLETADAS")

if __name__ == "__main__":
    asyncio.run(main())