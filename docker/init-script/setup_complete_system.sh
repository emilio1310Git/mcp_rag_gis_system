#!/bin/bash
# docker/scripts/setup_complete_system.sh
# Script para configurar el sistema completo con TimescaleDB

set -e

echo "🚀 Configurando Sistema MCP RAG GIS v2.0 con TimescaleDB"
echo "======================================================="

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

# Verificar Docker y Docker Compose
print_status "Verificando prerequisitos..."
if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose no está instalado"
    exit 1
fi

print_success "Docker y Docker Compose encontrados"

# Crear directorios necesarios
print_status "Creando estructura de directorios..."
mkdir -p {data/{documents,maps,chroma_db},logs/{nginx,app},docker/{grafana/{dashboards,provisioning/{dashboards,datasources}},nginx/conf.d,prometheus,alertmanager,init-scripts}}

# Crear archivo de configuración de PostgreSQL
print_status "Creando configuración de PostgreSQL..."
cat > docker/postgresql.conf << 'EOF'
# Configuración optimizada para TimescaleDB
shared_preload_libraries = 'timescaledb,pg_stat_statements'
max_connections = 100
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
min_wal_size = 1GB
max_wal_size = 4GB

# TimescaleDB específico
timescaledb.max_background_workers = 8
timescaledb.telemetry_level = off

# Configuración de log
log_destination = 'stderr'
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 1000
log_statement = 'all'
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
EOF

# Crear script de configuración PostGIS
print_status "Creando script de configuración PostGIS..."
cat > docker/postgis-setup.sql << 'EOF'
-- Configuración adicional PostGIS y pgRouting
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Configurar SRID personalizado si es necesario
INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) 
VALUES (999001, 'CUSTOM', 999001, 
        '+proj=utm +zone=30 +datum=WGS84 +units=m +no_defs', 
        'PROJCS["Custom UTM Zone 30N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-3],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1]]')
ON CONFLICT (srid) DO NOTHING;

SELECT 'PostGIS y pgRouting configurados correctamente' as status;
EOF

# Crear configuración de Nginx
print_status "Creando configuración de Nginx..."
cat > docker/nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Log format
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                   '$status $body_bytes_sent "$http_referer" '
                   '"$http_user_agent" "$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;
    
    # Configuración de compresión
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    
    # Configuración de archivos estáticos
    location /maps/ {
        alias /var/www/maps/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
    
    include /etc/nginx/conf.d/*.conf;
}
EOF

cat > docker/nginx/conf.d/default.conf << 'EOF'
# Proxy para API FastAPI
upstream fastapi_backend {
    server host.docker.internal:8000;
}

# Proxy para Grafana
upstream grafana_backend {
    server grafana:3000;
}

server {
    listen 80;
    server_name localhost;
    
    # API REST
    location /api/ {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
        add_header Access-Control-Allow-Headers "Origin, Content-Type, Accept, Authorization";
        
        if ($request_method = 'OPTIONS') {
            return 204;
        }
    }
    
    # Documentación de API
    location /docs {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Grafana dashboards
    location /grafana/ {
        proxy_pass http://grafana_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Mapas estáticos
    location /maps/ {
        alias /var/www/maps/;
        expires 1h;
        add_header Cache-Control "public, immutable";
        autoindex on;
    }
    
    # Página principal
    location / {
        return 302 /docs;
    }
}
EOF

# Crear configuración de Prometheus
print_status "Creando configuración de Prometheus..."
cat > docker/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'fastapi'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
EOF

# Crear reglas de alerta
cat > docker/prometheus/alert_rules.yml << 'EOF'
groups:
  - name: database_alerts
    rules:
      - alert: PostgreSQLDown
        expr: pg_up == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL instance is down"
          description: "PostgreSQL database is down for more than 5 minutes"

      - alert: HighDatabaseConnections
        expr: pg_stat_database_numbackends > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High number of database connections"
          description: "Number of database connections is above 80"

  - name: system_alerts
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is above 80% for more than 5 minutes"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is above 90% for more than 5 minutes"
EOF

# Crear configuración de Alertmanager
print_status "Creando configuración de Alertmanager..."
cat > docker/alertmanager/alertmanager.yml << 'EOF'
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alertmanager@example.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://host.docker.internal:8000/api/alertmanager/webhook'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
EOF

# Crear dashboards de Grafana
print_status "Creando dashboards de Grafana..."
mkdir -p docker/grafana/provisioning/dashboards
mkdir -p docker/grafana/provisioning/datasources

cat > docker/grafana/provisioning/datasources/datasources.yml << 'EOF'
apiVersion: 1

datasources:
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: dwgeo_timescale
    user: postgres
    secureJsonData:
      password: postgres_secure_2024
    jsonData:
      sslmode: disable
      postgresVersion: 1400
      timescaledb: true

  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: false
EOF

cat > docker/grafana/provisioning/dashboards/dashboards.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
EOF

# Crear archivo .env para el proyecto
print_status "Creando archivo de configuración del proyecto..."
cat > .env << 'EOF'
# Configuración de base de datos TimescaleDB
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dwgeo_timescale
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_secure_2024

# Configuración Ollama
OLLAMA_URL=http://localhost:11434
DEFAULT_MODEL=llama3.2
EMBEDDING_MODEL=nomic-embed-text

# Configuración API
API_HOST=localhost
API_PORT=8000
DEBUG=True

# Configuración Twilio (opcional)
TWILIO_ACCOUNT_SID=your_twilio_sid_here
TWILIO_AUTH_TOKEN=your_twilio_token_here
TWILIO_FROM_NUMBER=+1234567890

# Configuración Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis_secure_2024

# Rutas del proyecto
DOCUMENTS_DIR=./data/documents
VECTOR_DB_DIR=./data/chroma_db
MAPS_DIR=./data/maps
LOGS_DIR=./logs
EOF

# Crear script de inicio rápido
print_status "Creando script de inicio rápido..."
cat > scripts/quick_start.sh << 'EOF'
#!/bin/bash
echo "🚀 Iniciando Sistema MCP RAG GIS v2.0..."

# Iniciar servicios Docker
echo "📦 Iniciando servicios Docker..."
docker-compose -f docker/docker-compose.yml up -d

# Esperar que los servicios estén listos
echo "⏳ Esperando que los servicios estén listos..."
sleep 30

# Instalar modelos Ollama
echo "🤖 Instalando modelos Ollama..."
python scripts/install_ollama_models.py

# Configurar base de datos
echo "🗄️ Configurando base de datos..."
python scripts/setup_database.py

# Ejecutar tests
echo "🧪 Ejecutando tests del sistema..."
python tests/test_complete_system.py

echo "✅ Sistema iniciado correctamente!"
echo "🌐 Accesos disponibles:"
echo "  - API REST: http://localhost/docs"
echo "  - Grafana: http://localhost/grafana (admin/admin_secure_2024)"
echo "  - Prometheus: http://localhost:9090"
echo "  - Mapas: http://localhost/maps"
EOF

chmod +x scripts/quick_start.sh

# Crear documentos de ejemplo
print_status "Creando documentos de ejemplo..."
cat > data/documents/sistema_sensores.md << 'EOF'
# Sistema de Sensores de Temperatura

## Descripción
El sistema de monitoreo de temperatura utiliza sensores IoT distribuidos para detectar condiciones climáticas extremas y activar protocolos de emergencia.

## Tipos de Sensores
- **Sensores de temperatura**: Miden temperatura ambiente cada 5 minutos
- **Sensores de humedad**: Complementan las mediciones de temperatura
- **Sensores de calidad del aire**: Monitorizan partículas y gases

## Umbrales de Alerta
- **Calor extremo**: > 40°C
- **Frío extremo**: < 0°C
- **Cambio brusco**: Variación > 10°C en 1 hora

## Refugios de Emergencia
Los refugios están equipados con:
- Aire acondicionado y calefacción
- Servicio médico básico
- Comunicaciones de emergencia
- Suministro de agua y alimentos

## Protocolos de Evacuación
1. Detección automática de condiciones extremas
2. Activación de alertas SMS
3. Cálculo de rutas óptimas a refugios
4. Coordinación con servicios de emergencia
EOF

cat > data/documents/normativa_emergencias.md << 'EOF'
# Normativa de Emergencias Climáticas

## Marco Legal
La gestión de emergencias climáticas está regulada por:
- Ley 17/2015 del Sistema Nacional de Protección Civil
- Real Decreto 407/1992 sobre Planes de Emergencia
- Directiva 2007/60/CE sobre evaluación y gestión de riesgos

## Competencias
- **Estatal**: Coordinación general y recursos extraordinarios
- **Autonómica**: Planificación y gestión regional
- **Local**: Ejecución y primeros auxilios

## Protocolos de Activación
### Nivel 1 - Vigilancia
- Monitoreo continuo de condiciones
- Verificación de sistemas de alerta
- Preparación de recursos básicos

### Nivel 2 - Alerta
- Activación de protocolos preventivos
- Notificación a población vulnerable
- Preparación de refugios temporales

### Nivel 3 - Emergencia
- Evacuación de zonas de riesgo
- Activación completa de refugios
- Movilización de servicios de emergencia

## Derechos de los Ciudadanos
- Información clara y oportuna sobre riesgos
- Acceso a refugios y servicios básicos
- Asistencia médica y psicológica
- Compensación por daños documentados
EOF

print_success "Estructura de directorios creada"
print_success "Archivos de configuración generados"
print_success "Documentos de ejemplo creados"

echo ""
echo "🎉 Sistema configurado correctamente!"
echo ""
echo "📋 Próximos pasos:"
echo "1. Revisar y ajustar configuración en .env"
echo "2. Configurar credenciales de Twilio (opcional)"
echo "3. Ejecutar: ./scripts/quick_start.sh"
echo ""
echo "📖 Documentación:"
echo "- API REST: http://localhost/docs"
echo "- Grafana: http://localhost/grafana"
echo "- Mapas: http://localhost/maps"
echo ""