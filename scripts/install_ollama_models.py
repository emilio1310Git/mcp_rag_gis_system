"""Script para instalar modelos de Ollama"""

import subprocess
import sys
import time
import requests

def check_ollama_running():
    """Verificar si Ollama está funcionando"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def pull_model(model_name):
    """Descargar modelo de Ollama"""
    print(f"📥 Descargando modelo: {model_name}")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutos timeout
        )
        
        if result.returncode == 0:
            print(f"✅ {model_name} descargado correctamente")
            return True
        else:
            print(f"❌ Error descargando {model_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout descargando {model_name}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🤖 Instalando modelos de Ollama...")
    
    if not check_ollama_running():
        print("❌ Ollama no está funcionando. Inicia el servicio primero.")
        sys.exit(1)
    
    models = [
        "llama3.2",  # Modelo principal
        "nomic-embed-text"  # Modelo de embeddings
    ]
    
    for model in models:
        success = pull_model(model)
        if not success:
            print(f"⚠️ No se pudo descargar {model}")
        time.sleep(2)
    
    print("🎉 Instalación de modelos completada")

if __name__ == "__main__":
    main()