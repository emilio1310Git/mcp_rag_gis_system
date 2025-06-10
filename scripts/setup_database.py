#!/usr/bin/env python3
"""
Script para configurar y poblar la base de datos PostgreSQL/PostGIS del sistema

Este script gestiona:
- Verificación y configuración de la conexión a PostgreSQL
- Validación de extensiones PostGIS requeridas
- Creación y validación de tablas del sistema
- Población con datos de ejemplo
- Verificación de índices espaciales
- Diagnóstico completo del estado de la base de datos

Tablas gestionadas:
- secciones_censales: Divisiones administrativas con geometrías y datos poblacionales
- equipamientos: Servicios públicos con ubicaciones geoespaciales

Extensiones requeridas:
- PostGIS: Funcionalidades geoespaciales
- PostGIS Topology: Análisis topológicos avanzados
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

# Añadir src al path para importaciones del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.postgres_client import PostgreSQLClient
from config.settings import settings

# Configuración de logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class TableInfo:
    """
    Información de configuración para una tabla del sistema
    
    Attributes:
        name: Nombre de la tabla
        description: Descripción de la funcionalidad
        required_columns: Columnas que deben existir
        geometry_column: Columna espacial (si aplica)
        expected_srid: Sistema de coordenadas esperado
        has_spatial_index: Si debe tener índice espacial
    """
    name: str
    description: str
    required_columns: List[str]
    geometry_column: Optional[str] = None
    expected_srid: int = 4326
    has_spatial_index: bool = False

@dataclass
class ExtensionInfo:
    """
    Información sobre extensiones de PostgreSQL requeridas
    
    Attributes:
        name: Nombre de la extensión
        description: Descripción de funcionalidad
        required: Si es crítica para el funcionamiento
        version_check: Query para verificar versión (opcional)
    """
    name: str
    description: str
    required: bool = True
    version_check: Optional[str] = None

@dataclass
class DatabaseStatus:
    """
    Estado completo de la base de datos tras verificación
    
    Attributes:
        connection_ok: Si la conexión funciona
        extensions_ok: Si todas las extensiones están disponibles
        tables_ok: Si todas las tablas están correctas
        data_ok: Si hay datos de ejemplo cargados
        indexes_ok: Si los índices están optimizados
        total_issues: Número total de problemas encontrados
        recommendations: Lista de acciones recomendadas
    """
    connection_ok: bool = False
    extensions_ok: bool = False
    tables_ok: bool = False
    data_ok: bool = False
    indexes_ok: bool = False
    total_issues: int = 0
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []

class DatabaseSetup:
    """
    Configurador y validador completo de la base de datos PostgreSQL/PostGIS
    
    Responsabilidades:
    - Gestionar conexión y verificar configuración de BD
    - Validar y crear extensiones PostGIS
    - Verificar esquema de tablas y crear si es necesario
    - Poblar con datos de ejemplo para testing
    - Optimizar índices espaciales para rendimiento
    - Generar reportes de estado y recomendaciones
    """
    
    def __init__(self):
        """
        Inicializar el configurador de base de datos
        """
        self.client: Optional[PostgreSQLClient] = None
        
        # Definir extensiones requeridas
        self.required_extensions = [
            ExtensionInfo(
                name="postgis",
                description="Funcionalidades geoespaciales básicas",
                required=True,
                version_check="SELECT PostGIS_Version()"
            ),
            ExtensionInfo(
                name="postgis_topology", 
                description="Análisis topológicos avanzados",
                required=False,
                version_check="SELECT topology.topology_id FROM topology.topology LIMIT 1"
            )
        ]
        
        # Definir estructura de tablas esperada
        self.required_tables = [
            TableInfo(
                name="secciones_censales",
                description="Secciones censales con datos poblacionales y geometrías",
                required_columns=[
                    "id", "codigo_seccion", "codigo_distrito", "codigo_municipio",
                    "nombre_municipio", "poblacion", "superficie_km2", "densidad_hab_km2",
                    "geom", "created_at", "updated_at"
                ],
                geometry_column="geom",
                expected_srid=4326,
                has_spatial_index=True
            ),
            TableInfo(
                name="equipamientos",
                description="Equipamientos públicos con ubicaciones geoespaciales", 
                required_columns=[
                    "id", "nombre", "tipo", "direccion", "telefono", "website",
                    "horario_apertura", "capacidad", "publico", "geom",
                    "created_at", "updated_at"
                ],
                geometry_column="geom",
                expected_srid=4326,
                has_spatial_index=True
            )
        ]
        
        logger.info("🏗️ DatabaseSetup inicializado")
    
    async def initialize_client(self) -> bool:
        """
        Inicializar y verificar conexión con PostgreSQL
        
        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            logger.info("🔌 Conectando a PostgreSQL...")
            logger.info(f"   Host: {settings.database.host}:{settings.database.port}")
            logger.info(f"   Database: {settings.database.database}")
            logger.info(f"   User: {settings.database.username}")
            
            self.client = PostgreSQLClient()
            await self.client.initialize()
            
            # Verificar conexión con query básica
            result = await self.client.execute_query("SELECT version() as version, current_database() as database")
            
            if result:
                pg_version = result[0]['version']
                db_name = result[0]['database']
                logger.info(f"✅ Conexión exitosa a PostgreSQL")
                logger.info(f"   Versión: {pg_version.split(',')[0]}")  # Solo la parte principal
                logger.info(f"   Base de datos activa: {db_name}")
                return True
            else:
                logger.error("❌ No se pudo verificar la conexión")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error conectando a PostgreSQL: {e}")
            logger.error("💡 Verificar que PostgreSQL esté ejecutándose y las credenciales sean correctas")
            return False
    
    async def check_extensions(self) -> Tuple[bool, List[str]]:
        """
        Verificar y reportar estado de extensiones PostGIS
        
        Returns:
            Tupla con (todas_extensiones_ok, lista_de_problemas)
        """
        logger.info("🔍 Verificando extensiones de PostgreSQL...")
        
        issues = []
        extensions_ok = True
        
        # Obtener extensiones instaladas
        extensions_query = """
        SELECT extname, extversion 
        FROM pg_extension 
        WHERE extname IN ('postgis', 'postgis_topology')
        """
        
        try:
            installed_extensions = await self.client.execute_query(extensions_query)
            installed_names = {ext['extname']: ext['extversion'] for ext in installed_extensions}
            
            # Verificar cada extensión requerida
            for ext_info in self.required_extensions:
                if ext_info.name in installed_names:
                    version = installed_names[ext_info.name]
                    logger.info(f"✅ {ext_info.name} v{version} - {ext_info.description}")
                    
                    # Verificar funcionalidad con query específica si está definida
                    if ext_info.version_check:
                        try:
                            await self.client.execute_query(ext_info.version_check)
                            logger.debug(f"   Verificación funcional de {ext_info.name}: OK")
                        except Exception as e:
                            logger.warning(f"⚠️ Problema funcional con {ext_info.name}: {e}")
                            
                else:
                    if ext_info.required:
                        logger.error(f"❌ Extensión crítica faltante: {ext_info.name}")
                        issues.append(f"Instalar extensión {ext_info.name}")
                        extensions_ok = False
                    else:
                        logger.warning(f"⚠️ Extensión opcional faltante: {ext_info.name}")
                        issues.append(f"Considerar instalar {ext_info.name} para funcionalidad completa")
            
            return extensions_ok, issues
            
        except Exception as e:
            logger.error(f"❌ Error verificando extensiones: {e}")
            issues.append("Verificar permisos de base de datos para consultar extensiones")
            return False, issues
    
    async def check_tables(self) -> Tuple[bool, List[str]]:
        """
        Verificar estructura y estado de las tablas del sistema
        
        Returns:
            Tupla con (todas_tablas_ok, lista_de_problemas)
        """
        logger.info("🗄️ Verificando estructura de tablas...")
        
        issues = []
        tables_ok = True
        
        # Query para obtener información de tablas existentes
        tables_query = """
        SELECT 
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name IN ('secciones_censales', 'equipamientos')
        ORDER BY table_name, ordinal_position
        """
        
        try:
            table_columns = await self.client.execute_query(tables_query)
            
            # Agrupar columnas por tabla
            tables_found = {}
            for row in table_columns:
                table_name = row['table_name']
                if table_name not in tables_found:
                    tables_found[table_name] = []
                tables_found[table_name].append(row['column_name'])
            
            # Verificar cada tabla requerida
            for table_info in self.required_tables:
                if table_info.name in tables_found:
                    found_columns = set(tables_found[table_info.name])
                    required_columns = set(table_info.required_columns)
                    
                    # Verificar columnas faltantes
                    missing_columns = required_columns - found_columns
                    
                    if not missing_columns:
                        logger.info(f"✅ Tabla {table_info.name}: Estructura correcta ({len(found_columns)} columnas)")
                        
                        # Verificar geometría espacial si aplica
                        if table_info.geometry_column:
                            geometry_ok = await self._check_geometry_column(
                                table_info.name, 
                                table_info.geometry_column, 
                                table_info.expected_srid
                            )
                            if not geometry_ok:
                                issues.append(f"Verificar columna espacial {table_info.geometry_column} en {table_info.name}")
                                tables_ok = False
                                
                    else:
                        logger.error(f"❌ Tabla {table_info.name}: Columnas faltantes: {missing_columns}")
                        issues.append(f"Recrear tabla {table_info.name} con esquema completo")
                        tables_ok = False
                        
                else:
                    logger.error(f"❌ Tabla faltante: {table_info.name}")
                    issues.append(f"Crear tabla {table_info.name}")
                    tables_ok = False
            
            return tables_ok, issues
            
        except Exception as e:
            logger.error(f"❌ Error verificando tablas: {e}")
            issues.append("Verificar permisos de base de datos para consultar esquemas")
            return False, issues
    
    async def _check_geometry_column(self, table_name: str, column_name: str, expected_srid: int) -> bool:
        """
        Verificar configuración específica de columna geométrica
        
        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna geométrica  
            expected_srid: SRID esperado para la columna
            
        Returns:
            True si la configuración es correcta
        """
        try:
            geometry_query = """
            SELECT 
                coord_dimension,
                srid,
                type
            FROM geometry_columns 
            WHERE f_table_name = $1 AND f_geometry_column = $2
            """
            
            result = await self.client.execute_query(
                geometry_query, 
                {"table": table_name, "column": column_name}
            )
            
            if result:
                geom_info = result[0]
                srid = geom_info['srid']
                geom_type = geom_info['type']
                dimensions = geom_info['coord_dimension']
                
                if srid == expected_srid:
                    logger.debug(f"   Geometría {column_name}: {geom_type} SRID:{srid} ({dimensions}D) ✅")
                    return True
                else:
                    logger.warning(f"   Geometría {column_name}: SRID incorrecto {srid}, esperado {expected_srid}")
                    return False
            else:
                logger.warning(f"   Geometría {column_name}: No registrada en geometry_columns")
                return False
                
        except Exception as e:
            logger.warning(f"   Error verificando geometría {column_name}: {e}")
            return False
    
    async def check_data(self) -> Tuple[bool, List[str]]:
        """
        Verificar existencia y calidad de datos de ejemplo
        
        Returns:
            Tupla con (datos_ok, lista_de_problemas)
        """
        logger.info("📊 Verificando datos de ejemplo...")
        
        issues = []
        data_ok = True
        
        try:
            # Verificar datos en cada tabla
            for table_info in self.required_tables:
                count_query = f"SELECT COUNT(*) as count FROM {table_info.name}"
                result = await self.client.execute_query(count_query)
                
                if result:
                    count = result[0]['count']
                    if count > 0:
                        logger.info(f"✅ {table_info.name}: {count:,} registros")
                        
                        # Verificar calidad de datos geoespaciales si aplica
                        if table_info.geometry_column:
                            await self._check_spatial_data_quality(table_info.name, table_info.geometry_column)
                            
                    else:
                        logger.warning(f"⚠️ {table_info.name}: Sin datos")
                        issues.append(f"Poblar {table_info.name} con datos de ejemplo")
                        data_ok = False
                else:
                    logger.error(f"❌ No se pudo consultar {table_info.name}")
                    issues.append(f"Verificar accesibilidad de tabla {table_info.name}")
                    data_ok = False
            
            return data_ok, issues
            
        except Exception as e:
            logger.error(f"❌ Error verificando datos: {e}")
            issues.append("Verificar permisos de lectura en tablas")
            return False, issues
    
    async def _check_spatial_data_quality(self, table_name: str, geometry_column: str) -> None:
        """
        Verificar calidad de datos espaciales (geometrías válidas, no nulas, etc.)
        
        Args:
            table_name: Nombre de la tabla
            geometry_column: Nombre de la columna geométrica
        """
        try:
            # Verificar geometrías válidas
            validity_query = f"""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN {geometry_column} IS NOT NULL THEN 1 END) as with_geometry,
                COUNT(CASE WHEN ST_IsValid({geometry_column}) THEN 1 END) as valid_geometry
            FROM {table_name}
            """
            
            result = await self.client.execute_query(validity_query)
            
            if result:
                stats = result[0]
                total = stats['total']
                with_geom = stats['with_geometry']
                valid_geom = stats['valid_geometry']
                
                coverage = (with_geom / total * 100) if total > 0 else 0
                validity = (valid_geom / with_geom * 100) if with_geom > 0 else 0
                
                logger.debug(f"   Calidad espacial: {coverage:.1f}% cobertura, {validity:.1f}% válidas")
                
                if coverage < 90:
                    logger.warning(f"   ⚠️ Baja cobertura geométrica en {table_name}: {coverage:.1f}%")
                if validity < 95:
                    logger.warning(f"   ⚠️ Geometrías inválidas en {table_name}: {100-validity:.1f}%")
                    
        except Exception as e:
            logger.debug(f"   No se pudo verificar calidad espacial: {e}")
    
    async def check_indexes(self) -> Tuple[bool, List[str]]:
        """
        Verificar estado de índices espaciales y de rendimiento
        
        Returns:
            Tupla con (indices_ok, lista_de_problemas)
        """
        logger.info("⚡ Verificando índices de rendimiento...")
        
        issues = []
        indexes_ok = True
        
        # Query para obtener índices existentes
        indexes_query = """
        SELECT 
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND tablename IN ('secciones_censales', 'equipamientos')
        ORDER BY tablename, indexname
        """
        
        try:
            existing_indexes = await self.client.execute_query(indexes_query)
            
            # Agrupar índices por tabla
            table_indexes = {}
            for idx in existing_indexes:
                table_name = idx['tablename']
                if table_name not in table_indexes:
                    table_indexes[table_name] = []
                table_indexes[table_name].append({
                    'name': idx['indexname'],
                    'definition': idx['indexdef']
                })
            
            # Verificar índices requeridos para cada tabla
            for table_info in self.required_tables:
                table_name = table_info.name
                indexes = table_indexes.get(table_name, [])
                
                logger.info(f"📑 {table_name}: {len(indexes)} índices encontrados")
                
                # Verificar índice espacial si es requerido
                if table_info.has_spatial_index and table_info.geometry_column:
                    spatial_index_found = any(
                        'gist' in idx['definition'].lower() and table_info.geometry_column in idx['definition']
                        for idx in indexes
                    )
                    
                    if spatial_index_found:
                        logger.debug(f"   ✅ Índice espacial GIST presente para {table_info.geometry_column}")
                    else:
                        logger.warning(f"   ⚠️ Índice espacial GIST faltante para {table_info.geometry_column}")
                        issues.append(f"Crear índice espacial en {table_name}.{table_info.geometry_column}")
                        indexes_ok = False
                
                # Verificar otros índices importantes (primary key, unique constraints)
                pk_found = any('pkey' in idx['name'] for idx in indexes)
                if not pk_found:
                    logger.warning(f"   ⚠️ Clave primaria no encontrada en {table_name}")
                    issues.append(f"Verificar clave primaria en {table_name}")
                    indexes_ok = False
            
            return indexes_ok, issues
            
        except Exception as e:
            logger.error(f"❌ Error verificando índices: {e}")
            issues.append("Verificar permisos para consultar índices")
            return False, issues
    
    async def populate_sample_data(self) -> bool:
        """
        Poblar base de datos con datos de ejemplo si están vacías
        
        Returns:
            True si la población fue exitosa o no era necesaria
        """
        logger.info("🌱 Verificando necesidad de datos de ejemplo...")
        
        try:
            # Verificar si ya hay datos
            for table_info in self.required_tables:
                count_result = await self.client.execute_query(f"SELECT COUNT(*) as count FROM {table_info.name}")
                count = count_result[0]['count'] if count_result else 0
                
                if count == 0:
                    logger.info(f"📥 Poblando {table_info.name} con datos de ejemplo...")
                    success = await self._insert_sample_data(table_info.name)
                    if not success:
                        return False
                else:
                    logger.info(f"✅ {table_info.name} ya contiene {count:,} registros")
            
            logger.info("✅ Datos de ejemplo verificados/poblados correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error poblando datos de ejemplo: {e}")
            return False
    
    async def _insert_sample_data(self, table_name: str) -> bool:
        """
        Insertar datos de ejemplo específicos para una tabla
        
        Args:
            table_name: Nombre de la tabla a poblar
            
        Returns:
            True si la inserción fue exitosa
        """
        try:
            if table_name == "secciones_censales":
                insert_query = """
                INSERT INTO secciones_censales 
                (codigo_seccion, codigo_distrito, codigo_municipio, nombre_municipio, 
                 poblacion, superficie_km2, densidad_hab_km2, geom) 
                VALUES 
                ('2807901001', '01', '28079', 'Madrid', 1500, 0.5, 3000, 
                 ST_GeomFromText('POLYGON((-3.7038 40.4168, -3.7028 40.4168, -3.7028 40.4158, -3.7038 40.4158, -3.7038 40.4168))', 4326)),
                ('2807901002', '01', '28079', 'Madrid', 2200, 0.8, 2750, 
                 ST_GeomFromText('POLYGON((-3.7028 40.4168, -3.7018 40.4168, -3.7018 40.4158, -3.7028 40.4158, -3.7028 40.4168))', 4326)),
                ('0801402001', '02', '08014', 'Barcelona', 1800, 0.6, 3000, 
                 ST_GeomFromText('POLYGON((2.1734 41.3851, 2.1744 41.3851, 2.1744 41.3841, 2.1734 41.3841, 2.1734 41.3851))', 4326)),
                ('5001303001', '03', '50013', 'Zaragoza', 1200, 0.7, 1714, 
                 ST_GeomFromText('POLYGON((-0.8877 41.6488, -0.8867 41.6488, -0.8867 41.6478, -0.8877 41.6478, -0.8877 41.6488))', 4326))
                ON CONFLICT (codigo_seccion) DO NOTHING
                """
                
            elif table_name == "equipamientos":
                insert_query = """
                INSERT INTO equipamientos 
                (nombre, tipo, direccion, geom) 
                VALUES 
                ('Hospital Universitario La Paz', 'hospital', 'Paseo de la Castellana, 261, Madrid', 
                 ST_GeomFromText('POINT(-3.7033 40.4163)', 4326)),
                ('CEIP Ramón y Cajal', 'school', 'Calle de Arturo Soria, 52, Madrid', 
                 ST_GeomFromText('POINT(-3.7023 40.4163)', 4326)),
                ('Farmacia Central', 'pharmacy', 'Gran Vía, 123, Madrid', 
                 ST_GeomFromText('POINT(-3.7033 40.4153)', 4326)),
                ('Hospital Clínic', 'hospital', 'Carrer de Villarroel, 170, Barcelona', 
                 ST_GeomFromText('POINT(2.1739 41.3846)', 4326)),
                ('Biblioteca Pública Central', 'library', 'Plaza del Pilar, 1, Zaragoza', 
                 ST_GeomFromText('POINT(-0.8872 41.6483)', 4326))
                ON CONFLICT DO NOTHING
                """
            else:
                logger.warning(f"⚠️ No hay datos de ejemplo definidos para {table_name}")
                return True
            
            result = await self.client.execute_command(insert_query)
            
            # Contar registros insertados
            count_result = await self.client.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
            count = count_result[0]['count'] if count_result else 0
            
            logger.info(f"✅ Datos insertados en {table_name}: {count:,} registros totales")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error insertando datos en {table_name}: {e}")
            return False
    
    async def generate_status_report(self) -> DatabaseStatus:
        """
        Generar reporte completo del estado de la base de datos
        
        Returns:
            Objeto DatabaseStatus con estado detallado y recomendaciones
        """
        logger.info("📋 Generando reporte de estado de la base de datos...")
        
        status = DatabaseStatus()
        all_issues = []
        
        # 1. Verificar conexión
        status.connection_ok = await self.initialize_client()
        
        if not status.connection_ok:
            status.total_issues += 1
            status.recommendations.append("Verificar que PostgreSQL esté ejecutándose")
            status.recommendations.append("Comprobar credenciales de conexión en .env")
            return status
        
        # 2. Verificar extensiones
        status.extensions_ok, ext_issues = await self.check_extensions()
        all_issues.extend(ext_issues)
        
        # 3. Verificar tablas
        status.tables_ok, table_issues = await self.check_tables()
        all_issues.extend(table_issues)
        
        # 4. Verificar datos
        status.data_ok, data_issues = await self.check_data()
        all_issues.extend(data_issues)
        
        # 5. Verificar índices
        status.indexes_ok, index_issues = await self.check_indexes()
        all_issues.extend(index_issues)
        
        # 6. Poblar datos si es necesario
        if status.tables_ok and not status.data_ok:
            logger.info("🌱 Intentando poblar con datos de ejemplo...")
            if await self.populate_sample_data():
                status.data_ok = True
                logger.info("✅ Datos de ejemplo poblados correctamente")
            else:
                all_issues.append("No se pudieron insertar datos de ejemplo")
        
        # Compilar reporte final
        status.total_issues = len(all_issues)
        status.recommendations = all_issues
        
        return status
    
    def print_status_report(self, status: DatabaseStatus) -> None:
        """
        Imprimir reporte visual del estado de la base de datos
        
        Args:
            status: Estado de la base de datos a mostrar
        """
        print("\n" + "="*70)
        print("🗄️ REPORTE DE ESTADO - BASE DE DATOS POSTGRESQL/POSTGIS")
        print("="*70)
        
        # Estado general
        components = [
            ("🔌 Conexión", status.connection_ok),
            ("🧩 Extensiones PostGIS", status.extensions_ok),
            ("🗄️ Estructura de tablas", status.tables_ok),
            ("📊 Datos de ejemplo", status.data_ok), 
            ("⚡ Índices optimizados", status.indexes_ok)
        ]
        
        print("📋 Estado de componentes:")
        for name, ok in components:
            status_icon = "✅" if ok else "❌"
            print(f"  {status_icon} {name}")
        
        # Cálculo de salud general
        healthy_components = sum(1 for _, ok in components if ok)
        health_percentage = (healthy_components / len(components)) * 100
        
        print(f"\n🎯 Salud general: {health_percentage:.0f}% ({healthy_components}/{len(components)} componentes)")
        
        # Estado general
        if health_percentage >= 90:
            print("🟢 ESTADO: EXCELENTE - Base de datos completamente funcional")
        elif health_percentage >= 70:
            print("🟡 ESTADO: BUENO - Funcional con problemas menores")
        elif health_percentage >= 50:
            print("🟠 ESTADO: REGULAR - Requiere atención")
        else:
            print("🔴 ESTADO: CRÍTICO - Problemas graves detectados")
        
        # Información de configuración
        print(f"\n⚙️ Configuración de conexión:")
        print(f"  • Host: {settings.database.host}:{settings.database.port}")
        print(f"  • Base de datos: {settings.database.database}")
        print(f"  • Usuario: {settings.database.username}")
        
        # Problemas y recomendaciones
        if status.total_issues > 0:
            print(f"\n⚠️ Problemas detectados ({status.total_issues}):")
            for i, issue in enumerate(status.recommendations, 1):
                print(f"  {i}. {issue}")
            
            print(f"\n💡 Acciones recomendadas:")
            print(f"  • Ejecutar: docker-compose -f docker/docker-compose.yml up -d")
            print(f"  • Verificar logs: docker-compose -f docker/docker-compose.yml logs postgres")
            print(f"  • Revisar configuración en archivo .env")
            
        else:
            print(f"\n🎉 ¡Perfecto! No se detectaron problemas")
            print(f"  • Base de datos lista para el sistema MCP RAG GIS")
            print(f"  • Todas las funcionalidades geoespaciales disponibles")
        
        # Información de tablas si está todo OK
        if status.connection_ok and status.tables_ok:
            print(f"\n📊 Información de tablas:")
            try:
                # Esta información se obtendría del cliente, pero para el reporte la simulamos
                print(f"  • secciones_censales: Divisiones administrativas con geometrías")
                print(f"  • equipamientos: Servicios públicos geolocalizados")
            except:
                pass
        
        print("="*70 + "\n")
    
    async def cleanup(self) -> None:
        """
        Limpiar recursos y cerrar conexiones
        """
        if self.client:
            try:
                await self.client.close()
                logger.info("🧹 Conexión de base de datos cerrada")
            except Exception as e:
                logger.warning(f"⚠️ Error cerrando conexión: {e}")

async def setup_database() -> bool:
    """
    Función principal para configurar y verificar la base de datos
    
    Flujo completo:
    1. Inicializar configurador y conectar
    2. Verificar extensiones PostGIS
    3. Validar estructura de tablas
    4. Comprobar datos y poblar si es necesario
    5. Optimizar índices espaciales
    6. Generar reporte de estado
    
    Returns:
        True si la configuración fue exitosa, False en caso contrario
    """
    setup = DatabaseSetup()
    
    try:
        logger.info("🚀 Iniciando configuración de base de datos PostgreSQL/PostGIS")
        
        # Generar reporte completo de estado
        status = await setup.generate_status_report()
        
        # Mostrar reporte visual
        setup.print_status_report(status)
        
        # Determinar éxito basado en componentes críticos
        critical_components_ok = (
            status.connection_ok and 
            status.extensions_ok and 
            status.tables_ok
        )
        
        if critical_components_ok:
            logger.info("✅ Configuración de base de datos completada exitosamente")
            
            # Mostrar información adicional si todo está bien
            if status.data_ok and status.indexes_ok:
                logger.info("🎯 Sistema listo para análisis geoespaciales avanzados")
                logger.info("🗺️ Funcionalidades disponibles:")
                logger.info("   • Análisis de cobertura de equipamientos")
                logger.info("   • Join espacial con secciones censales")
                logger.info("   • Búsqueda de ubicaciones óptimas")
                logger.info("   • Mapas interactivos con PostGIS")
            
            return True
        else:
            logger.error("❌ Configuración de base de datos falló")
            logger.error("💡 Revisar los problemas reportados arriba")
            return False
            
    except Exception as e:
        logger.error(f"💥 Error fatal en configuración de base de datos: {e}")
        return False
        
    finally:
        await setup.cleanup()

async def quick_health_check() -> Dict[str, Any]:
    """
    Verificación rápida de salud de la base de datos
    
    Función ligera para verificaciones periódicas sin setup completo
    
    Returns:
        Diccionario con estado básico de la base de datos
    """
    client = None
    try:
        client = PostgreSQLClient()
        await client.initialize()
        
        # Test básico de conectividad
        result = await client.execute_query("SELECT 1 as test")
        connection_ok = result and result[0]['test'] == 1
        
        # Contar registros en tablas principales
        tables_status = {}
        for table in ['secciones_censales', 'equipamientos']:
            try:
                count_result = await client.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                tables_status[table] = count_result[0]['count'] if count_result else 0
            except:
                tables_status[table] = -1  # Error
        
        return {
            "timestamp": datetime.now().isoformat(),
            "connection_ok": connection_ok,
            "tables": tables_status,
            "total_records": sum(count for count in tables_status.values() if count > 0)
        }
        
    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "connection_ok": False,
            "error": str(e),
            "tables": {},
            "total_records": 0
        }
    finally:
        if client:
            await client.close()

def main() -> None:
    """
    Punto de entrada principal del script
    
    Maneja argumentos de línea de comandos y ejecuta la función apropiada
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Configurador de base de datos PostgreSQL/PostGIS para sistema MCP RAG GIS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python setup_database.py              # Configuración completa
  python setup_database.py --check      # Solo verificación rápida
  python setup_database.py --verbose    # Con logging detallado
        """
    )
    
    parser.add_argument(
        "--check", 
        action="store_true",
        help="Realizar solo verificación rápida de salud"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true", 
        help="Habilitar logging detallado (DEBUG)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON (útil para scripts)"
    )
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Modo verbose habilitado")
    
    try:
        if args.check:
            # Verificación rápida
            logger.info("⚡ Ejecutando verificación rápida de salud...")
            health = asyncio.run(quick_health_check())
            
            if args.json:
                print(json.dumps(health, indent=2))
            else:
                print(f"\n📊 Verificación rápida de salud:")
                print(f"  🔌 Conexión: {'✅' if health['connection_ok'] else '❌'}")
                print(f"  📊 Registros totales: {health['total_records']:,}")
                for table, count in health['tables'].items():
                    if count >= 0:
                        print(f"    • {table}: {count:,}")
                    else:
                        print(f"    • {table}: ❌ Error")
            
            sys.exit(0 if health['connection_ok'] else 1)
        else:
            # Configuración completa
            success = asyncio.run(setup_database())
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("⌨️ Operación cancelada por el usuario")
        sys.exit(130)  # Código estándar para interrupción
    except Exception as e:
        logger.error(f"💥 Error fatal no manejado: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()