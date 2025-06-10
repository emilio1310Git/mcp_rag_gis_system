
"""Test completo del sistema MCP RAG GIS v2.0"""

import asyncio
import sys
import os
import logging
from pathlib import Path
import requests
import time

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemTester:
    """Tester completo del sistema"""
    
    def __init__(self):
        self.success_count = 0
        self.total_tests = 0
        self.failed_tests = []
    
    def test_result(self, test_name: str, success: bool, message: str = ""):
        """Registrar resultado de test"""
        self.total_tests += 1
        if success:
            self.success_count += 1
            logger.info(f"✅ {test_name}: {message}")
        else:
            self.failed_tests.append(test_name)
            logger.error(f"❌ {test_name}: {message}")
        return success
    
    async def test_imports(self):
        """Test 1: Verificar importaciones"""
        try:
            from config.settings import settings
            assert settings is not None
            self.test_result("Configuración", True, "Settings cargado correctamente")
            
            from services.rag_service import RAGService
            self.test_result("RAG Service", True, "Importación exitosa")
            
            from services.maps_service import MapsService
            self.test_result("Maps Service", True, "Importación exitosa")
            
            from services.gis_service import GISService
            self.test_result("GIS Service", True, "Importación exitosa")
            
            from database.postgres_client import PostgreSQLClient
            self.test_result("PostgreSQL Client", True, "Importación exitosa")
            
            return True
            
        except Exception as e:
            self.test_result("Importaciones", False, f"Error: {e}")
            return False
    
    async def test_rag_system(self):
        """Test 2: Sistema RAG"""
        try:
            from services.rag_service import RAGService
            
            rag_service = RAGService()
            
            # Test inicialización
            try:
                await rag_service.initialize()
                self.test_result("RAG Inicialización", True, "Ollama conectado")
                
                # Test info vectorstore
                info = await rag_service.get_vectorstore_info()
                self.test_result("RAG Vectorstore Info", True, f"Status: {info['status']}")
                
                # Test listado de documentos
                docs_path = Path("data/documents")
                if docs_path.exists():
                    docs = await rag_service.list_documents(str(docs_path))
                    self.test_result("RAG List Documents", True, f"Encontrados {len(docs)} documentos")
                    
                    if docs:
                        # Test procesamiento de documentos
                        processed_docs = await rag_service.process_documents(str(docs_path))
                        if processed_docs:
                            self.test_result("RAG Process Documents", True, f"Procesados {len(processed_docs)} chunks")
                            
                            # Test creación de vectorstore
                            success = await rag_service.create_vectorstore(processed_docs)
                            self.test_result("RAG Create Vectorstore", success, "Vectorstore creado")
                            
                            if success:
                                # Test consulta
                                result = await rag_service.query("¿Qué equipamientos se mencionan?")
                                if "error" not in result:
                                    self.test_result("RAG Query", True, f"Respuesta: {result['answer'][:50]}...")
                                else:
                                    self.test_result("RAG Query", False, result['error'])
                        else:
                            self.test_result("RAG Process Documents", False, "No se procesaron documentos")
                    else:
                        self.test_result("RAG Documents", False, "No hay documentos para procesar")
                else:
                    self.test_result("RAG Documents Path", False, "Directorio de documentos no existe")
                    
            except Exception as e:
                self.test_result("RAG Sistema", False, f"Ollama no disponible: {e}")
                
        except Exception as e:
            self.test_result("RAG Test", False, f"Error: {e}")
    
    async def test_maps_system(self):
        """Test 3: Sistema de mapas"""
        try:
            from services.maps_service import MapsService
            
            maps_service = MapsService()
            
            # Test geocodificación
            try:
                lat, lon = await maps_service.geocode_address("Madrid, España")
                if 40.0 < lat < 41.0 and -4.0 < lon < -3.0:
                    self.test_result("Maps Geocoding", True, f"Madrid: {lat:.4f}, {lon:.4f}")
                    
                    # Test búsqueda de equipamientos
                    facilities = await maps_service.find_facilities_nearby(lat, lon, 2000)
                    total_facilities = sum(len(f_list) for f_list in facilities.values())
                    self.test_result("Maps Find Facilities", True, f"Encontrados {total_facilities} equipamientos")
                    
                    if total_facilities > 0:
                        # Test creación de mapa
                        map_filename = await maps_service.create_interactive_map(
                            "Madrid, España", lat, lon, facilities
                        )
                        
                        map_path = Path("data/maps") / map_filename
                        if map_path.exists():
                            self.test_result("Maps Create Map", True, f"Mapa creado: {map_filename}")
                        else:
                            self.test_result("Maps Create Map", False, "Archivo de mapa no creado")
                    
                else:
                    self.test_result("Maps Geocoding", False, "Coordenadas incorrectas para Madrid")
                    
            except Exception as e:
                self.test_result("Maps Geocoding", False, f"Error: {e}")
                
        except Exception as e:
            self.test_result("Maps Test", False, f"Error: {e}")
    
    async def test_database_system(self):
        """Test 4: Sistema de base de datos"""
        try:
            from database.postgres_client import PostgreSQLClient
            
            client = PostgreSQLClient()
            
            try:
                await client.initialize()
                self.test_result("DB Connection", True, "PostgreSQL conectado")
                
                # Test consulta básica
                result = await client.execute_query("SELECT 1 as test")
                if result and result[0]['test'] == 1:
                    self.test_result("DB Basic Query", True, "Consulta básica exitosa")
                    
                    # Test tablas del sistema
                    tables_query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name IN ('secciones_censales', 'equipamientos')
                    """
                    
                    tables = await client.execute_query(tables_query)
                    table_names = [t['table_name'] for t in tables]
                    
                    if 'secciones_censales' in table_names:
                        self.test_result("DB Secciones Table", True, "Tabla secciones_censales existe")
                        
                        # Contar secciones
                        count_result = await client.execute_query("SELECT COUNT(*) as count FROM secciones_censales")
                        section_count = count_result[0]['count']
                        self.test_result("DB Secciones Data", section_count > 0, f"Secciones: {section_count}")
                    else:
                        self.test_result("DB Secciones Table", False, "Tabla secciones_censales no existe")
                    
                    if 'equipamientos' in table_names:
                        self.test_result("DB Equipamientos Table", True, "Tabla equipamientos existe")
                        
                        # Contar equipamientos
                        count_result = await client.execute_query("SELECT COUNT(*) as count FROM equipamientos")
                        equipment_count = count_result[0]['count']
                        self.test_result("DB Equipamientos Data", equipment_count > 0, f"Equipamientos: {equipment_count}")
                    else:
                        self.test_result("DB Equipamientos Table", False, "Tabla equipamientos no existe")
                        
                await client.close()
                
            except Exception as e:
                self.test_result("DB Connection", False, f"PostgreSQL no disponible: {e}")
                
        except Exception as e:
            self.test_result("DB Test", False, f"Error: {e}")
    
    async def test_gis_system(self):
        """Test 5: Sistema GIS"""
        try:
            from services.gis_service import GISService
            from database.postgres_client import postgres_client
            
            gis_service = GISService()
            
            try:
                await postgres_client.initialize()
                
                # Test obtención de secciones censales
                sections = await gis_service.get_census_sections()
                self.test_result("GIS Census Sections", not sections.empty, f"Secciones obtenidas: {len(sections)}")
                
                # Test análisis de cobertura (si hay datos)
                if not sections.empty:
                    try:
                        coverage = await gis_service.analyze_facility_coverage("hospital", 2000)
                        if coverage:
                            self.test_result("GIS Coverage Analysis", True, 
                                           f"Cobertura hospitales: {coverage.get('porcentaje_poblacion_cubierta', 0):.1f}%")
                        else:
                            self.test_result("GIS Coverage Analysis", False, "Sin datos de cobertura")
                    except Exception as e:
                        self.test_result("GIS Coverage Analysis", False, f"Error: {e}")
                    
                    # Test ubicaciones óptimas
                    try:
                        optimal_locs = await gis_service.find_optimal_locations("library", 2)
                        self.test_result("GIS Optimal Locations", len(optimal_locs) > 0, 
                                       f"Ubicaciones óptimas: {len(optimal_locs)}")
                    except Exception as e:
                        self.test_result("GIS Optimal Locations", False, f"Error: {e}")
                
                await postgres_client.close()
                
            except Exception as e:
                self.test_result("GIS System", False, f"Error de conexión: {e}")
                
        except Exception as e:
            self.test_result("GIS Test", False, f"Error: {e}")
    
    async def test_api_system(self):
        """Test 6: Sistema API REST"""
        try:
            # Verificar si la API está corriendo
            api_url = "http://localhost:8000"
            
            try:
                response = requests.get(f"{api_url}/health", timeout=5)
                if response.status_code == 200:
                    self.test_result("API Health", True, "API respondiendo")
                    
                    # Test endpoint de tipos de equipamientos
                    response = requests.get(f"{api_url}/api/maps/facility-types", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        self.test_result("API Facility Types", True, f"Tipos: {len(data['facility_types'])}")
                    else:
                        self.test_result("API Facility Types", False, f"Status: {response.status_code}")
                    
                    # Test geocodificación via API
                    response = requests.get(
                        f"{api_url}/api/maps/geocode",
                        params={"address": "Madrid"},
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        self.test_result("API Geocoding", True, 
                                       f"Madrid: {data['latitude']:.4f}, {data['longitude']:.4f}")
                    else:
                        self.test_result("API Geocoding", False, f"Status: {response.status_code}")
                        
                else:
                    self.test_result("API Health", False, f"Status: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                self.test_result("API Connection", False, "API no está ejecutándose en puerto 8000")
            except requests.exceptions.Timeout:
                self.test_result("API Timeout", False, "API no responde en tiempo esperado")
                
        except Exception as e:
            self.test_result("API Test", False, f"Error: {e}")
    
    async def test_file_structure(self):
        """Test 7: Estructura de archivos"""
        try:
            required_paths = [
                "src/config/settings.py",
                "src/services/rag_service.py",
                "src/services/maps_service.py", 
                "src/services/gis_service.py",
                "src/database/postgres_client.py",
                "src/mcp_servers/rag_server.py",
                "src/mcp_servers/maps_server.py",
                "src/mcp_servers/gis_server.py",
                "src/api/main.py",
                "data/documents",
                "data/maps",
                "scripts/run_servers.py",
                "requirements.txt",
                ".env"
            ]
            
            missing_files = []
            for path in required_paths:
                if not Path(path).exists():
                    missing_files.append(path)
            
            if not missing_files:
                self.test_result("File Structure", True, "Todos los archivos necesarios presentes")
            else:
                self.test_result("File Structure", False, f"Archivos faltantes: {missing_files}")
                
        except Exception as e:
            self.test_result("File Structure Test", False, f"Error: {e}")
    
    def print_summary(self):
        """Imprimir resumen de tests"""
        print("\n" + "="*60)
        print("📊 RESUMEN DE TESTS DEL SISTEMA MCP RAG GIS v2.0")
        print("="*60)
        
        success_rate = (self.success_count / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"✅ Tests exitosos: {self.success_count}/{self.total_tests}")
        print(f"📈 Tasa de éxito: {success_rate:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Tests fallidos ({len(self.failed_tests)}):")
            for test in self.failed_tests:
                print(f"  - {test}")
        
        print("\n🎯 ESTADO DEL SISTEMA:")
        if success_rate >= 90:
            print("🟢 EXCELENTE - Sistema completamente funcional")
        elif success_rate >= 75:
            print("🟡 BUENO - Sistema mayormente funcional con problemas menores")
        elif success_rate >= 50:
            print("🟠 REGULAR - Sistema parcialmente funcional, requiere atención")
        else:
            print("🔴 CRÍTICO - Sistema con problemas graves, requiere revisión")
        
        print("\n💡 RECOMENDACIONES:")
        if "DB Connection" in self.failed_tests:
            print("  - Iniciar PostgreSQL: docker-compose -f docker/docker-compose.yml up -d")
        if "RAG Sistema" in self.failed_tests:
            print("  - Instalar modelos Ollama: python scripts/install_ollama_models.py")
        if "API Connection" in self.failed_tests:
            print("  - Iniciar API: python src/api/main.py")
        if "Maps Geocoding" in self.failed_tests:
            print("  - Verificar conexión a internet para geocodificación")
        
        print("\n🚀 Para iniciar el sistema completo:")
        print("  1. docker-compose -f docker/docker-compose.yml up -d")
        print("  2. python scripts/install_ollama_models.py")
        print("  3. python scripts/run_servers.py")
        print("  4. python src/api/main.py (en otra terminal)")

async def main():
    """Función principal de tests"""
    print("🧪 INICIANDO TESTS COMPLETOS DEL SISTEMA MCP RAG GIS v2.0")
    print("="*60)
    
    tester = SystemTester()
    
    # Ejecutar todos los tests
    await tester.test_file_structure()
    await tester.test_imports()
    await tester.test_database_system()
    await tester.test_rag_system()
    await tester.test_maps_system()
    await tester.test_gis_system()
    await tester.test_api_system()
    
    # Mostrar resumen
    tester.print_summary()
    
    # Código de salida basado en éxito
    success_rate = (tester.success_count / tester.total_tests * 100) if tester.total_tests > 0 else 0
    return 0 if success_rate >= 75 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)