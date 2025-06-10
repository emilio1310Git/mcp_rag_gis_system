import subprocess
import json
import time

def test_mcp_server_simple():
    """Prueba simple de un servidor MCP"""
    
    # Iniciar servidor RAG
    process = subprocess.Popen(
        ["python", "-m", "src.mcp_servers.rag_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Mensaje de inicialización
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize", 
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }
        
        # Enviar y leer
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        print("Inicialización:", response.strip())
        
        # Lista de herramientas
        tools_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        print("Herramientas:", response.strip())
        
        # Llamar herramienta
        call_msg = {
            "jsonrpc": "2.0", 
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_vectorstore_info",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(call_msg) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        print("Resultado:", response.strip())
        
    finally:
        process.terminate()

if __name__ == "__main__":
    test_mcp_server_simple()