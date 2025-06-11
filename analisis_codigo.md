# Explicación detallada de los ficheros y directorios del proyecto MCP RAG GIS System

> ⚠️ **Nota:** Este listado puede estar incompleto debido a limitaciones de la API. Consulta el [listado completo en GitHub](https://github.com/emilio1310Git/mcp_rag_gis_system/tree/main) para ver todo el contenido.

---

## Índice general

| Tipo         | Nombre                   | Descripción breve                                    |
|--------------|--------------------------|------------------------------------------------------|
| Archivo      | `.env.sample`            | Plantilla de variables de entorno                    |
| Archivo      | `.gitignore`             | Exclusión de archivos/directorios en git             |
| Carpeta      | `data/`                  | Documentos, mapas y bases vectoriales                |
| Archivo      | `debug_rag.py`           | Script de depuración para el sistema RAG             |
| Carpeta      | `docker/`                | Configuración de contenedores Docker                 |
| Archivo      | `implementacion.md`      | Documentación detallada de la implementación         |
| Archivo      | `pyproject.toml`         | Configuración de proyecto Python (poetry, build...)  |
| Archivo      | `requirements.txt`       | Listado de dependencias Python                      |
| Carpeta      | `scripts/`               | Scripts de instalación, arranque y utilidades        |
| Carpeta      | `src/`                   | Código fuente principal (módulos, servicios, API)    |
| Carpeta      | `test/`                  | Pruebas unitarias y de integración                   |

---

## Explicación y evaluación de ficheros y carpetas

### 1. `.env.sample`
**Función:**  
Plantilla de configuración de variables de entorno (claves, rutas, credenciales DB, etc).

**Uso:**  
- Copiar a `.env` y personalizar para el entorno local/producción.
- Ejemplo:
  ```
  cp .env.sample .env
  # Editar y configurar
  ```

**Posibles mejoras:**  
- Añadir ejemplos de valores realistas y comentarios explicativos.
- Separar variables sensibles del resto.

---

### 2. `.gitignore`
**Función:**  
Define patrones de archivos y carpetas que *no* deben incluirse en el control de versiones.

**Uso:**  
- Protege la privacidad y evita subir archivos temporales, de entorno o datos sensibles.

**Posibles mejoras:**  
- Revisar y actualizar para nuevas dependencias o entornos (por ejemplo, `/data`, `/venv`, `.env`).

---

### 3. `data/`
**Función:**  
Almacena datos de entrada/salida, documentos fuente, bases vectoriales y mapas generados.

**Uso:**  
- Guardar documentos para procesamiento RAG.
- Almacenar resultados de mapas y análisis GIS.

**Ejemplo de estructura:**
```
data/
├── docs/
├── maps/
├── vectorstore/
```
**Posibles mejoras:**  
- Añadir subcarpetas bien definidas.
- Incluir un README en `data/` para explicar la estructura.

---

### 4. `debug_rag.py`
**Función:**  
Herramienta para depurar el flujo de procesamiento RAG (embeddings, búsqueda vectorial, etc).

**Uso:**
- Lanzar pruebas manuales de consulta sobre documentos cargados.
- Revisar logs y debugging detallados.

**Ejemplo de uso:**
```bash
python debug_rag.py --query "¿Cuál es la normativa vigente?"
```

**Posibles mejoras:**
- Añadir un modo interactivo.
- Permitir selección de modelo y fuente de datos por parámetros.

---

### 5. `docker/`
**Función:**  
Contiene archivos para desplegar servicios con Docker (por ejemplo, `docker-compose.yml`, Dockerfiles para PostGIS, Ollama, etc).

**Uso:**  
- Desplegar la infraestructura completa con un solo comando.
- Ejemplo:
  ```bash
  docker-compose -f docker/docker-compose.yml up -d
  ```

**Posibles mejoras:**
- Documentar cada servicio en un README dentro de `docker/`.
- Añadir tests de salud (`healthcheck`) en los servicios.

---

### 6. `implementacion.md`
**Función:**  
Documentación extensa de la arquitectura, instalación, ejemplos de uso, flujo de trabajo, testing, etc.

**Uso:**  
- Referencia técnica para desarrolladores e integradores.
- Consultar diagramas, flujos y recomendaciones de despliegue.

**Mejoras:**  
- Mantener siempre sincronizado con el código.
- Añadir un índice navegable y enlaces internos.

---

### 7. `pyproject.toml`
**Función:**  
Archivo de configuración estándar Python para gestión de dependencias, build system, metadata, etc.

**Uso:**  
- Compatible con **poetry**, **pip**, **build**, etc.
- Ejemplo:
  ```bash
  poetry install
  ```

**Mejoras:**  
- Unificar dependencias con `requirements.txt` para evitar duplicidades.
- Documentar scripts custom si los hubiera.

---

### 8. `requirements.txt`
**Función:**  
Listado plano de dependencias Python para uso directo con pip.

**Uso:**  
```bash
pip install -r requirements.txt
```
**Mejoras:**  
- Generar automáticamente desde `pyproject.toml` si se usa poetry.

---

### 9. `scripts/`
**Función:**  
Scripts para instalación, despliegue, arranque y utilidades (por ejemplo: `install_system.sh`, `run_servers.py`, `setup_database.py`).

**Estructura y ejemplos:**
```
scripts/
├── install_system.sh         # Instalación automatizada
├── run_servers.py            # Arranca todos los microservicios MCP
├── setup_database.py         # Inicializa y valida la DB PostGIS
├── install_ollama_models.py  # Descarga y prepara modelos IA
```
**Ejemplo de uso:**
```bash
./scripts/install_system.sh
python scripts/run_servers.py
```

**Mejoras:**  
- Añadir ayuda (`-h`, `--help`) en todos los scripts Python.
- Documentar en README de la carpeta `scripts/`.

---

### 10. `src/`
**Función:**  
Contiene todo el código fuente del sistema: configuración, servicios, servidores MCP, API FastAPI, utilidades, etc.

**Estructura sugerida:**
```
src/
├── config/
├── database/
├── services/
├── mcp_servers/
├── api/
├── utils/
```

**Mejoras:**
- Añadir docstrings y type hints en todos los módulos.
- Documentar ejemplos de uso en cada paquete.

### 10.1 Main, Routers, lista de endpoints

#### 10.1.a `src/api/main.py`

**Función:**
Punto de entrada principal de la API FastAPI. Se encarga de crear la aplicación, incluir routers principales (GIS, Maps), definir middlewares y exponer rutas adicionales, como la descarga visualización de mapas estáticos generados. Permite servir no solo JSON sino también archivos HTML y otros resultados generados por el sistema.

**Responsabilidad principal:**

- Inicializar la instancia de FastAPI.
- Registrar routers (`gis`, `maps`) con sus prefijos y etiquetas.
- Definir rutas adicionales (como `/map/{map_filename}`).
- Configurar middlewares opcionales (CORS, autenticación, logging...).
- Publicar la documentación automática OpenAPI/Swagger.
- Ejecutar tareas de arranque/limpieza si es necesario.

##### 🏗️ Esquema básico realista:

```python
from fastapi import FastAPI
from .routers import gis, maps
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="MCP RAG GIS API",
    description="API REST para análisis geoespacial y mapas interactivos.",
    version="2.0"
)

app.include_router(gis.router, prefix='/api/gis', tags=["GIS"])
app.include_router(maps.router, prefix='/api/maps', tags=["Maps"])

MAPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/maps'))

@app.get("/map/{map_filename}", response_class=FileResponse, tags=["Static Maps"])
def serve_map(map_filename: str):
    """
    Devuelve un archivo de mapa generado (HTML, PNG, etc) por nombre de archivo.
    """
    file_path = os.path.join(MAPS_DIR, map_filename)
    if not os.path.isfile(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Mapa no encontrado")
    return file_path

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

------

##### 🛠️ Ejemplo de uso (despliegue local):

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

------

##### 🌐 Ejemplo de acceso a la documentación automática

- Swagger UI: http://localhost:8000/docs
- Redoc: http://localhost:8000/redoc

------

##### 🚩 **EndPoint directo: `/map/{map_filename}`**

| Método | Endpoint              | Descripción                                                  |
| ------ | --------------------- | ------------------------------------------------------------ |
| GET    | `/map/{map_filename}` | Devuelve el archivo de un mapa generado (HTML o imagen) según el nombre |

**Ejemplos de uso:**

- *Descargar un mapa HTML generado:*
    `/map/coverage_Madrid.html`
- *Obtener un PNG de un mapa de hospitales:*
    `/map/hospitals_centro.png`
- *Obtener un mapa de accesibilidad:*
    `/map/accessibility_report_28079.html`

**Respuesta esperada:**

- Archivo binario (HTML, PNG, SVG, etc.), mostrado en navegador o descargado.

**Errores posibles:**

- 404 si el archivo no existe.
- 403 si el archivo está fuera de la carpeta autorizada (mejora de seguridad recomendable).

------

##### 💡 Evaluación y posibles mejoras

| Aspecto        | Observaciones/Mejoras                                        |
| -------------- | ------------------------------------------------------------ |
| Modularidad    | Correcta, routers separados y rutas adicionales claras.      |
| Seguridad      | Comprobar rutas relativas (proteger de path traversal en `/map/{map_filename}`). |
| Documentación  | Añadir ejemplos y descripción clara en Swagger para `/map/{map_filename}`. |
| Configuración  | Permitir definir la ruta de la carpeta de mapas por variable de entorno. |
| Robustez       | Mejorar manejo de errores y logging.                         |
| Extensibilidad | Permitir servir diferentes formatos (GeoJSON, PDF, etc.) si se integran. |

------

#### 10.1.b `src/api/routers/gis.py`

**Función:**
Implementa los endpoints REST relacionados con el análisis geoespacial avanzado (GIS) usando FastAPI. Orquesta las llamadas a servicios GIS internos (buffer, cobertura, localización óptima, generación de mapas, informes de accesibilidad, etc.) y sirve como punto de entrada para los clientes que requieren análisis espaciales.

**Responsabilidad principal:**

- Definir rutas HTTP para operaciones GIS.
- Validar parámetros y datos de entrada (usando Pydantic).
- Llamar a los servicios correspondientes y devolver respuestas estructuradas.

##### 📋 Endpoints principales (simulados, adaptar a los reales si hay cambios):

| Método | Endpoint                        | Descripción                                      |
| ------ | ------------------------------- | ------------------------------------------------ |
| GET    | `/api/gis/census_sections`      | Listar secciones censales                        |
| POST   | `/api/gis/spatial_analysis`     | Análisis espacial de equipamientos               |
| GET    | `/api/gis/coverage_report`      | Informe de cobertura de servicios                |
| GET    | `/api/gis/optimal_locations`    | Buscar ubicaciones óptimas para nuevos servicios |
| GET    | `/api/gis/accessibility_report` | Informe de accesibilidad para una zona o tipo    |
| GET    | `/api/gis/coverage_map`         | Generar mapa de cobertura GIS                    |

##### 🛠️ Ejemplo de uso de cada endpoint

**1. GET `/api/gis/census_sections`**

- *Uso básico:*
    `/api/gis/census_sections`
- *Filtro por municipio:*
    `/api/gis/census_sections?municipio=Madrid`
- *Filtro por código censal:*
    `/api/gis/census_sections?section_id=28079001`

**2. POST `/api/gis/spatial_analysis`**

- *Ejemplo 1:*
    Body: `{ "facility_type": "hospital", "buffer_radius": 500 }`
- *Ejemplo 2:*
    Body: `{ "facility_type": "school", "buffer_radius": 300, "district": "Centro" }`
- *Ejemplo 3:*
    Body: `{ "facility_type": "library", "buffer_radius": 1000, "section_ids": [12345, 67890] }`

**3. GET `/api/gis/coverage_report`**

- *Por distrito:*
    `/api/gis/coverage_report?district=Retiro`
- *Por sección censal:*
    `/api/gis/coverage_report?section_id=28079002`
- *Por tipo de equipamiento:*
    `/api/gis/coverage_report?type=school`

**4. GET `/api/gis/optimal_locations`**

- *Por tipo de equipamiento:*
    `/api/gis/optimal_locations?type=hospital`
- *Por distrito:*
    `/api/gis/optimal_locations?type=school&district=Centro`
- *Por parámetros avanzados:*
    `/api/gis/optimal_locations?type=library&max_results=5&min_population=1000`

**5. GET `/api/gis/accessibility_report`**

- *Por sección censal:*
    `/api/gis/accessibility_report?section_id=28079001`
- *Por distrito:*
    `/api/gis/accessibility_report?district=Salamanca`
- *Por tipo y radio:*
    `/api/gis/accessibility_report?type=school&radius=500`

**6. GET `/api/gis/coverage_map`**

- *Por tipo de servicio:*
    `/api/gis/coverage_map?type=hospital`
- *Por distrito:*
    `/api/gis/coverage_map?district=Centro`
- *Con filtros avanzados:*
    `/api/gis/coverage_map?type=school&district=Retiro&format=png`

------

##### 💡 Evaluación y posibles mejoras

| Aspecto       | Observaciones/Mejoras                                        |
| ------------- | ------------------------------------------------------------ |
| Modularidad   | Muy buena, pero sería óptimo separar lógica de negocio de la definición de rutas. |
| Validación    | Revisar exhaustividad de validaciones de entrada (Pydantic). |
| Documentación | Asegurar que todos los endpoints tengan docstrings y ejemplos en Swagger. |
| Seguridad     | Añadir autenticación/autorización según el caso de uso.      |
| Pruebas       | Incluir tests para cada endpoint y escenarios de error.      |
| Optimización  | Revisar eficiencia en operaciones espaciales si el volumen de datos crece. |

------

#### 10.1.c `src/api/routers/maps.py`

**Función:**
Gestiona los endpoints REST relacionados con la generación y consulta de mapas interactivos y la búsqueda de equipamientos públicos usando datos de OpenStreetMap. Este router permite a los usuarios obtener mapas personalizados, localizar servicios y visualizar equipamientos en distintas zonas geográficas.

**Responsabilidad principal:**

- Definir rutas HTTP específicas para mapas y equipamientos.
- Recibir y validar parámetros geográficos (latitud, longitud, tipo de servicio, etc).
- Llamar a los servicios internos de mapas y devolver datos o archivos (HTML, imágenes).

##### 📋 Endpoints principales (ejemplo estándar):

| Método | Endpoint                     | Descripción                                           |
| ------ | ---------------------------- | ----------------------------------------------------- |
| GET    | `/api/maps/nearest_services` | Busca equipamientos públicos cercanos a una ubicación |
| GET    | `/api/maps/generate_map`     | Genera y devuelve un mapa interactivo personalizado   |
| GET    | `/api/maps/equipment_types`  | Lista los tipos de equipamientos soportados           |
| GET    | `/api/maps/service_location` | Da detalles de un equipamiento público específico     |

##### 🛠️ Ejemplo de uso de cada endpoint

**1. GET `/api/maps/nearest_services`**

- *Búsqueda básica:*
    `/api/maps/nearest_services?lat=40.4&lon=-3.7&type=hospital`
- *Con radio de búsqueda:*
    `/api/maps/nearest_services?lat=41.4&lon=2.1&type=school&radius=500`
- *Listar varios tipos:*
    `/api/maps/nearest_services?lat=39.5&lon=-0.4&type=hospital,school,library`

**2. GET `/api/maps/generate_map`**

- *Mapa de hospitales en Madrid:*
    `/api/maps/generate_map?city=Madrid&type=hospital`
- *Mapa de escuelas en un distrito:*
    `/api/maps/generate_map?district=Centro&type=school`
- *Mapa personalizado con varios tipos:*
    `/api/maps/generate_map?city=Barcelona&type=hospital,school&format=png`

**3. GET `/api/maps/equipment_types`**

- *Lista simple:*
    `/api/maps/equipment_types`
- *Filtrado por disponibilidad:*
    `/api/maps/equipment_types?available=true`
- *Ejemplo de respuesta:*
    `["hospital", "school", "library", "sports_center"]`

**4. GET `/api/maps/service_location`**

- *Por ID de equipamiento:*
    `/api/maps/service_location?id=12345`
- *Por coordenadas:*
    `/api/maps/service_location?lat=40.4&lon=-3.7&type=library`
- *Detalle con metadatos:*
    `/api/maps/service_location?id=67890&details=true`

------

##### 💡 Evaluación y posibles mejoras

| Aspecto       | Observaciones/Mejoras                                        |
| ------------- | ------------------------------------------------------------ |
| Respuesta     | Permitir formatos alternativos (GeoJSON, PNG, HTML).         |
| Documentación | Añadir ejemplos reales y docstrings en Swagger para cada endpoint. |
| Validación    | Mejorar validación y control de errores para coordenadas y tipos de servicio. |
| Seguridad     | Limitar generación de mapas muy grandes o abusivos (por recursos). |
| Tests         | Tests unitarios y de integración para rutas y servicios críticos. |


---

### 10.2 Services y utils

#### 📁 src/services/

**Función general:**
Contiene la lógica de negocio centralizada y desacoplada de la API, agrupando las operaciones principales del sistema: procesamiento RAG, generación de mapas, análisis GIS y utilidades de integración con modelos y bases de datos. Los routers llaman a estos servicios para mantener el código modular y reutilizable.

------

##### 1. `src/services/rag_service.py`

**Función:**
Gestiona la recuperación aumentada de información (RAG) sobre los documentos cargados. Orquesta el flujo: ingesta, generación de embeddings, consulta semántica, recuperación de fuentes, etc.

**Responsabilidades:**

- Indexar y almacenar documentos.
- Generar y consultar embeddings vectoriales.
- Integrar modelos Ollama y LangChain para respuestas aumentadas.
- Devolver resultados con referencias y metadatos.

**Ejemplo de uso:**

```python
from src.services.rag_service import answer_query

response = answer_query(
    question="¿Cuál es la normativa vigente para parques?",
    document_source="docs/urbanismo.pdf"
)
```

**Posibles mejoras:**

- Añadir cache de resultados frecuentes.
- Permitir consultas multi-documento.
- Mejorar control de versiones de los embeddings.

------

##### 2. `src/services/maps_service.py`

**Función:**
Gestiona la lógica de generación de mapas interactivos y búsqueda de equipamientos públicos usando datos de OpenStreetMap y Folium.

**Responsabilidades:**

- Geocodificar ubicaciones.
- Buscar equipamientos por tipo (hospital, escuela, etc.).
- Generar mapas HTML o imágenes.
- Calcular distancias, rutas y ranking de servicios.

**Ejemplo de uso:**

```python
from src.services.maps_service import generate_map

html_map = generate_map(
    city="Madrid",
    types=["hospital", "school"],
    highlight="hospital"
)
```

**Posibles mejoras:**

- Permitir diferentes estilos de visualización de mapas.
- Optimizar el manejo de grandes volúmenes de puntos.
- Añadir soporte para exportar a GeoJSON.

------

##### 3. `src/services/gis_service.py`

**Función:**
Encapsula el análisis geoespacial avanzado usando PostgreSQL/PostGIS. Realiza operaciones de buffer, cobertura, accesibilidad y búsqueda de ubicaciones óptimas.

**Responsabilidades:**

- Obtener secciones censales y demografía.
- Realizar joins espaciales entre equipamientos y zonas.
- Calcular cobertura y accesibilidad.
- Generar informes, métricas y visualizaciones GIS.

**Ejemplo de uso:**

```python
from src.services.gis_service import analyze_coverage

report = analyze_coverage(
    district="Centro",
    facility_type="hospital"
)
```

**Posibles mejoras:**

- Añadir algoritmos de optimización multi-criterio.
- Mejorar validación de geometrías y entradas.
- Integrar visualizaciones automáticas de resultados.

------

##### 💡 Tabla resumen y mejoras por cada servicio

| Servicio        | Responsabilidad principal                  | Mejora sugerida                          |
| --------------- | ------------------------------------------ | ---------------------------------------- |
| rag_service.py  | Consultas RAG, embeddings, IA              | Cache, multi-documento, versionado       |
| maps_service.py | Mapas, geocodificación, búsqueda OSM       | Exportar GeoJSON, más estilos            |
| gis_service.py  | Análisis espacial, cobertura, informes GIS | Algoritmos avanzados, auto-visualización |

#### 📁 src/utils/

**Función general:**
Contiene utilidades, helpers y funciones comunes compartidas por los servicios principales. Aquí se centralizan las operaciones auxiliares para evitar duplicidad de código.

**Estructura típica:**

```
src/utils/
├── geocoding_utils.py
├── formatting_utils.py
├── spatial_utils.py
├── file_utils.py
└── logging_utils.py
```

------

##### 1. `geocoding_utils.py`

**Función:**
Proporciona funciones para geocodificación directa/inversa, validación y parseo de coordenadas, integración con servicios externos como Nominatim.

**Ejemplo de uso:**

```python
from src.utils.geocoding_utils import geocode_address

lat, lon = geocode_address("Calle Mayor, Madrid")
```

**Posibles mejoras:**

- Añadir soporte para caché de resultados
- Validación robusta de direcciones

------

##### 2. `formatting_utils.py`

**Función:**
Helpers para formatear datos de salida, construir respuestas API, convertir datos a GeoJSON o CSV.

**Ejemplo de uso:**

```python
from src.utils.formatting_utils import to_geojson

geojson = to_geojson(points_list)
```

**Posibles mejoras:**

- Soportar más formatos de exportación

------

##### 3. `spatial_utils.py`

**Función:**
Funciones para cálculo espacial: distancias, buffers, intersecciones y validación de geometrías.

**Ejemplo de uso:**

```python
from src.utils.spatial_utils import distance

d = distance((40.4, -3.7), (40.5, -3.6))
```

**Posibles mejoras:**

- Optimización para grandes lotes de datos

------

##### 4. `file_utils.py`

**Función:**
Gestión de archivos: lectura/escritura segura, manejo de rutas, comprobación de extensiones soportadas.

**Ejemplo de uso:**

```python
from src.utils.file_utils import safe_read

content = safe_read("data/docs/plan.pdf")
```

**Posibles mejoras:**

- Manejo de grandes archivos y streams

------

##### 5. `logging_utils.py` (si existe)

**Función:**
Configuración y helpers para logging estructurado en todo el sistema.

**Ejemplo de uso:**

```python
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)
logger.info("Servicio iniciado")
```

**Posibles mejoras:**

- Integrar con sistemas externos de monitorización

------

##### 💡 Tabla resumen de utilidades

| Utilidad            | Responsabilidad principal        | Mejora sugerida                      |
| ------------------- | -------------------------------- | ------------------------------------ |
| geocoding_utils.py  | Geocodificación y validación     | Cache, validación avanzada           |
| formatting_utils.py | Formato de salida (GeoJSON, etc) | Más formatos, validaciones           |
| spatial_utils.py    | Cálculo espacial                 | Optimización, soporte batch          |
| file_utils.py       | Gestión de archivos              | Streams, manejo de errores avanzados |
| *logging_utils.py*  | *Logging estructurado*           | *Integraciones externas*             |

------

#### 📊 Esquema de dependencias de servicios

```mermaid
graph TD
    API[API Routers]
    RAG[RAG Service]
    MAPS[Maps Service]
    GIS[GIS Service]
    UTILS[(Utils -módulos-)]
    DB[(PostgreSQL/PostGIS)]
    OLLAMA[(Ollama + LangChain)]
    API --> RAG
    API --> MAPS
    API --> GIS
    RAG --> OLLAMA
    RAG -.-> UTILS
    MAPS -.-> UTILS
    GIS --> DB
    GIS -.-> UTILS
```

- Las líneas punteadas (`-.->`) indican uso de utilidades, no una dependencia de servicio formal.
- `Utils` representa un conjunto de módulos auxiliares a los que acceden los servicios según necesidad, no un servicio aparte.
- El flujo principal es: **los Routers llaman a los Services, y los Services usan los módulos de Utils cuando lo necesitan**.
- No existe una dependencia directa de OLLAMA hacia UTILS, sino desde RAG Service hacia ambos.

---

> **Nota:** Este esquema refleja de forma fiel la arquitectura modular del sistema y ayuda a visualizar la relación entre los componentes principales y las utilidades compartidas.

------

### 10.3 MCP SERVERS

#### 📁 src/mcp_servers/

**Función general:**
Contiene los servidores MCP (Microservicios de Coordinación y Procesamiento) específicos de la plataforma, cada uno encargado de una funcionalidad o flujo independiente dentro de la arquitectura. Estos servidores encapsulan la lógica de integración y orquestación entre módulos, modelos de IA, base de datos y servicios externos.

**Estructura típica esperada:**

```
src/mcp_servers/
├── mcp_rag_server.py
├── mcp_maps_server.py
├── mcp_gis_server.py
└── __init__.py
```

------

##### 1. `mcp_rag_server.py`

**Función:**
Servidor dedicado a la orquestación del flujo RAG (Retrieval Augmented Generation). Gestiona la ingesta de documentos, el almacenamiento y consulta de embeddings, la interacción con modelos de lenguaje y la composición de respuestas enriquecidas.

**Responsabilidades:**

- Lógica principal para consultas RAG.
- Orquestación de llamadas a bases vectoriales, modelos Ollama/LangChain.
- Exposición de endpoints internos para su uso por la API o scripts.

**Ejemplo de uso:**

```python
from src.mcp_servers.mcp_rag_server import launch_rag_server

launch_rag_server(config_path="config/rag_settings.yaml")
```

**Mejoras sugeridas:**

- Añadir autenticación de endpoints internos.
- Permitir configuración dinámica de modelos y fuentes de datos.
- Instrumentar logs y métricas de uso.

------

##### 2. `mcp_maps_server.py`

**Función:**
Servidor encargado de la gestión y generación de mapas interactivos, integración con datos de OpenStreetMap y lógica de visualización geográfica.

**Responsabilidades:**

- Generación de mapas según parámetros de consulta.
- Orquestación de búsquedas y filtros sobre datos OSM.
- Exposición de endpoints internos para obtener mapas o datos geoespaciales preprocesados.

**Ejemplo de uso:**

```python
from src.mcp_servers.mcp_maps_server import run_maps_server

run_maps_server(host="0.0.0.0", port=8500)
```

**Mejoras sugeridas:**

- Permitir exportar mapas en múltiples formatos (HTML, PNG, GeoJSON).
- Añadir control de acceso y límites de recursos.

------

##### 3. `mcp_gis_server.py`

**Función:**
Servidor dedicado a operaciones GIS avanzadas: análisis espacial, cobertura, buffers, informes de accesibilidad y consulta de datos censales/demográficos usando PostGIS.

**Responsabilidades:**

- Procesar consultas espaciales complejas de forma eficiente.
- Ofrecer endpoints internos para análisis GIS bajo demanda.
- Orquestar la integración con la base de datos PostGIS y los servicios de utilidades espaciales.

**Ejemplo de uso:**

```python
from src.mcp_servers.mcp_gis_server import start_gis_server

start_gis_server(db_url="postgresql://user:pass@localhost/db")
```

**Mejoras sugeridas:**

- Añadir cache de resultados de análisis costosos.
- Soportar operaciones batch y consultas asíncronas.
- Mejorar la validación y robustez ante errores de datos.

------

##### 4. `__init__.py`

**Función:**
Marca el directorio como un paquete Python y permite importar los servidores desde `src.mcp_servers`.

------

##### 💡 Tabla resumen y posibles mejoras

| Servidor           | Responsabilidad principal     | Mejora sugerida                         |
| ------------------ | ----------------------------- | --------------------------------------- |
| mcp_rag_server.py  | Orquestación y consultas RAG  | Autenticación, configuración dinámica   |
| mcp_maps_server.py | Generación y gestión de mapas | Exportación formatos, control de acceso |
| mcp_gis_server.py  | Análisis GIS avanzado         | Cache, batch, robustez en validación    |
| **init**.py        | Paquete Python                | -                                       |

------

##### 📈 Diagrama de integración MCP Servers

```mermaid
graph TD
    API[API Routers]
    RAG_SRV[MCP RAG Server]
    MAPS_SRV[MCP Maps Server]
    GIS_SRV[MCP GIS Server]
    SERVICES[Services Layer]
    UTILS[[Utils]]
    DB[(PostgreSQL/PostGIS)]
    OLLAMA[(Ollama + LangChain)]
    
    API --> RAG_SRV
    API --> MAPS_SRV
    API --> GIS_SRV
    RAG_SRV --> SERVICES
    MAPS_SRV --> SERVICES
    GIS_SRV --> SERVICES
    RAG_SRV --> OLLAMA
    RAG_SRV -.-> UTILS
    MAPS_SRV -.-> UTILS
    GIS_SRV --> DB
    GIS_SRV -.-> UTILS
```

- Las líneas continuas muestran integración y dependencias principales.
- Las líneas punteadas (`-.->`) indican uso auxiliar de utilidades.


------

### 11. `test/`
**Función:**  
Pruebas unitarias y de integración para validar el sistema.

**Uso:**  
```bash
pytest test/
```
**Mejoras:**  
- Añadir pruebas de regresión y cobertura.
- Incluir fixtures con ejemplos realistas.

---

## Ejemplo de uso de endpoints (API FastAPI)

Supongamos que hay un endpoint `/api/maps/nearest_services`:

| Método | Endpoint                          | Descripción breve                  | Ejemplo de uso                               |
|--------|-----------------------------------|------------------------------------|----------------------------------------------|
| GET    | `/api/maps/nearest_services`      | Devuelve servicios públicos cercanos| `/api/maps/nearest_services?lat=40.4&lon=-3.7&type=hospital` |
| POST   | `/api/rag/query`                  | Consulta RAG sobre documentos       | JSON: `{ "question": "..." }`               |
| GET    | `/api/gis/coverage_report`        | Informe de cobertura por distrito   | `/api/gis/coverage_report?district=Centro`  |

### Ejemplo 1: `/api/maps/nearest_services`
- **Descripción:** Busca equipamientos públicos más cercanos a una ubicación.
- **Ejemplo 1:** `/api/maps/nearest_services?lat=40.4&lon=-3.7&type=hospital`
- **Ejemplo 2:** `/api/maps/nearest_services?lat=41.4&lon=2.1&type=school`
- **Ejemplo 3:** `/api/maps/nearest_services?lat=37.4&lon=-5.9&type=library`

### Ejemplo 2: `/api/rag/query`
- **Descripción:** Consulta inteligente sobre documentos cargados.
- **Ejemplo 1:** `POST /api/rag/query` con body `{ "question": "¿Cuál es la normativa vigente para parques?" }`
- **Ejemplo 2:** `POST /api/rag/query` con body `{ "question": "Resumen ejecutivo del plan urbanístico." }`
- **Ejemplo 3:** `POST /api/rag/query` con body `{ "question": "¿Qué equipamientos faltan en el distrito Centro?" }`

### Ejemplo 3: `/api/gis/coverage_report`
- **Descripción:** Informe GIS de cobertura de servicios.
- **Ejemplo 1:** `/api/gis/coverage_report?district=Centro`
- **Ejemplo 2:** `/api/gis/coverage_report?section=12345`
- **Ejemplo 3:** `/api/gis/coverage_report?type=hospital`

---

## Esquema general del sistema

```mermaid
graph TD
    subgraph Infraestructura
        D1[Docker: PostgreSQL + PostGIS]
        D2[Docker: Ollama]
    end
    subgraph Backend
        S1[Servidor MCP RAG]
        S2[Servidor MCP Maps]
        S3[Servidor MCP GIS]
        API[API FastAPI]
    end
    subgraph Datos
        V1[ChromaDB]
        F1[Documentos, Mapas, Vectorstore]
    end
    D1 --> S3
    D2 --> S1
    V1 --> S1
    F1 --> S1
    S1 --> API
    S2 --> API
    S3 --> API
    API --> Usuario
```

---

## Tabla de posibles mejoras globales

| Elemento         | Mejora sugerida                                    |
|------------------|---------------------------------------------------|
| `.env.sample`    | Añadir comentarios y ejemplos de valores           |
| `data/`          | README explicativo y subcarpetas ordenadas         |
| `docker/`        | Documentar cada servicio y añadir healthchecks     |
| `scripts/`       | Ayuda CLI, documentación y manejo de errores      |
| `src/`           | Docstrings, type hints, ejemplos de integración    |
| `test/`          | Casos realistas, regressión y fixtures             |
| Endpoints        | Más ejemplos y validación de entrada               |
| Documentación    | Índice navegable, enlaces internos, diagramas      |

---

> Consulta el repositorio completo aquí: [emilio1310Git/mcp_rag_gis_system](https://github.com/emilio1310Git/mcp_rag_gis_system)