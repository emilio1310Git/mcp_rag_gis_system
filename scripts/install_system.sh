# scripts/install_system.sh
#!/bin/bash

echo "🚀 Instalando Sistema MCP RAG GIS v2.0..."

# Variables
PROJECT_NAME="mcp_rag_gis_system"
PYTHON_VERSION="3.10"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Verificar Python
print_status "Verificando Python ${PYTHON_VERSION}+"
if ! python3 --version | grep -q "Python 3.1[0-9]"; then
    print_error "Python 3.10+ requerido"
    exit 1
fi
print_success "Python verificado"

# 2. Crear estructura de directorios
print_status "Creando estructura del proyecto..."
mkdir -p ${PROJECT_NAME}/{src/{config,database,services,mcp_servers,api,utils},data/{documents,chroma_db,maps},logs,tests,scripts,docker}

cd ${PROJECT_NAME}

# 3. Crear entorno virtual
print_status "Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# 4. Actualizar pip
print_status "Actualizando pip..."
pip install --upgrade pip

# 5. Instalar dependencias
print_status "Instalando dependencias..."
cat > requirements.txt << 'EOF'
# Core MCP
mcp>=1.1.0

# LangChain actualizado
langchain>=0.3.1
langchain-ollama>=0.2.0
langchain-core>=0.3.1
langchain-chroma>=0.1.4

# Base de datos y vectores
chromadb>=0.5.0
psycopg2-binary>=2.9.9

# Geoespacial
geopandas>=1.0.1
shapely>=2.0.4
folium>=0.16.0
overpy>=0.7
geopy>=2.4.1

# API y web
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0

# Procesamiento de datos
pandas>=2.2.0
numpy>=1.26.0
PyPDF2>=3.0.1

# Utilidades
python-multipart>=0.0.9
requests>=2.31.0
python-dotenv>=1.0.0

# Desarrollo
pytest>=8.0.0
black>=24.0.0
isort>=5.13.0
EOF

pip install -r requirements.txt

# 6. Crear archivo de configuración
print_status "Creando configuración..."
cat > .env << 'EOF'
# Configuración de base de datos PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gis_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Configuración Ollama
OLLAMA_URL=http://localhost:11434
DEFAULT_MODEL=llama3.2
EMBEDDING_MODEL=nomic-embed-text

# Configuración API
API_HOST=localhost
API_PORT=8000
DEBUG=True

# Logging
LOG_LEVEL=INFO
EOF

# 7. Crear docker-compose para PostgreSQL
print_status "Configurando PostgreSQL con PostGIS..."
cat > docker/docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgis/postgis:15-3.3
    container_name: gis_postgres
    environment:
      POSTGRES_DB: gis_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres-init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  ollama:
    image: ollama/ollama
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    command: serve
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
EOF

# 8. Crear script de inicialización de PostgreSQL
cat > docker/postgres-init.sql << 'EOF'
-- Habilitar extensiones PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Crear tabla de secciones censales
CREATE TABLE IF NOT EXISTS secciones_censales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_seccion VARCHAR(20) UNIQUE NOT NULL,
    codigo_distrito VARCHAR(10) NOT NULL,
    codigo_municipio VARCHAR(10) NOT NULL,
    nombre_municipio VARCHAR(100) NOT NULL,
    poblacion INTEGER DEFAULT 0,
    superficie_km2 FLOAT DEFAULT 0.0,
    densidad_hab_km2 FLOAT DEFAULT 0.0,
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla de equipamientos
CREATE TABLE IF NOT EXISTS equipamientos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(200) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    direccion VARCHAR(300),
    telefono VARCHAR(20),
    website VARCHAR(200),
    horario_apertura VARCHAR(100),
    capacidad INTEGER,
    publico BOOLEAN DEFAULT TRUE,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices espaciales
CREATE INDEX IF NOT EXISTS idx_secciones_geom ON secciones_censales USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_equipamientos_geom ON equipamientos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_equipamientos_tipo ON equipamientos (tipo);
CREATE INDEX IF NOT EXISTS idx_secciones_municipio ON secciones_censales (nombre_municipio);

-- Insertar datos de ejemplo
INSERT INTO secciones_censales (codigo_seccion, codigo_distrito, codigo_municipio, nombre_municipio, poblacion, superficie_km2, densidad_hab_km2, geom) VALUES
('2807901001', '01', '28079', 'Madrid', 1500, 0.5, 3000, ST_GeomFromText('POLYGON((-3.7038 40.4168, -3.7028 40.4168, -3.7028 40.4158, -3.7038 40.4158, -3.7038 40.4168))', 4326)),
('2807901002', '01', '28079', 'Madrid', 2200, 0.8, 2750, ST_GeomFromText('POLYGON((-3.7028 40.4168, -3.7018 40.4168, -3.7018 40.4158, -3.7028 40.4158, -3.7028 40.4168))', 4326)),
('0801402001', '02', '08014', 'Barcelona', 1800, 0.6, 3000, ST_GeomFromText('POLYGON((2.1734 41.3851, 2.1744 41.3851, 2.1744 41.3841, 2.1734 41.3841, 2.1734 41.3851))', 4326))
ON CONFLICT (codigo_seccion) DO NOTHING;

-- Insertar equipamientos de ejemplo
INSERT INTO equipamientos (nombre, tipo, direccion, geom) VALUES
('Hospital Universitario La Paz', 'hospital', 'Paseo de la Castellana, 261, Madrid', ST_GeomFromText('POINT(-3.7033 40.4163)', 4326)),
('CEIP Ramón y Cajal', 'school', 'Calle de Arturo Soria, 52, Madrid', ST_GeomFromText('POINT(-3.7023 40.4163)', 4326)),
('Farmacia Central', 'pharmacy', 'Gran Vía, 123, Madrid', ST_GeomFromText('POINT(-3.7033 40.4153)', 4326)),
('Hospital Clínic', 'hospital', 'Carrer de Villarroel, 170, Barcelona', ST_GeomFromText('POINT(2.1739 41.3846)', 4326))
ON CONFLICT DO NOTHING;

-- Crear función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Crear triggers para actualizar timestamp
CREATE TRIGGER update_secciones_updated_at BEFORE UPDATE ON secciones_censales FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_equipamientos_updated_at BEFORE UPDATE ON equipamientos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EOF

# 9. Crear script para instalar modelos Ollama
print_status "Creando script de modelos Ollama..."
cat > scripts/install_ollama_models.py << 'EOF'
#!/usr/bin/env python3
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
EOF

chmod +x scripts/install_ollama_models.py