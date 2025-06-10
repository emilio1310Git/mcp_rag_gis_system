#!/usr/bin/env python3
"""
Script principal para ejecutar todos los servidores MCP del sistema RAG GIS v2.0

Este script gestiona de forma centralizada:
- Servidor MCP RAG: Procesamiento de documentos y consultas inteligentes
- Servidor MCP Maps: Mapas básicos y búsqueda de equipamientos  
- Servidor MCP GIS: Análisis geoespacial avanzado con PostgreSQL

Funcionalidades:
- Inicio secuencial y controlado de servidores
- Monitorización continua del estado
- Cierre limpio y seguro de todos los procesos
- Manejo robusto de errores y señales del sistema
"""

import asyncio
import subprocess
import sys
import signal
import time
import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

# Configuración de logging con formato estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """
    Configuración de un servidor MCP individual
    
    Attributes:
        name: Nombre descriptivo del servidor
        module_path: Ruta del módulo Python (formato src.mcp_servers.server_name)
        description: Descripción de las funcionalidades del servidor
        critical: Si es True, el fallo de este servidor detiene todo el sistema
    """
    name: str
    module_path: str
    description: str
    critical: bool = True

class ServerManager:
    """
    Gestor centralizado de servidores MCP
    
    Responsabilidades:
    - Iniciar y detener servidores de forma controlada
    - Monitorizar el estado de los procesos
    - Manejar señales del sistema (Ctrl+C, SIGTERM)
    - Proporcionar logging detallado de operaciones
    """
    
    def __init__(self) -> None:
        """
        Inicializar el gestor de servidores
        
        Inicializa las estructuras de datos y configura los servidores disponibles
        """
        # Diccionario que mapea nombre_servidor -> proceso subprocess
        self.processes: Dict[str, subprocess.Popen] = {}
        
        # Flag que controla el bucle de monitorización
        self.running: bool = False
        
        # Directorio raíz del proyecto
        self.project_root = Path(__file__).parent.parent
        
        # Configuración de los servidores MCP disponibles
        self.server_configs: List[ServerConfig] = [
            ServerConfig(
                name="RAG",
                module_path="src.mcp_servers.rag_server",
                description="Procesamiento de documentos y consultas RAG con LangChain + Ollama",
                critical=True
            ),
            ServerConfig(
                name="Maps", 
                module_path="src.mcp_servers.maps_server",
                description="Mapas interactivos y búsqueda de equipamientos via OpenStreetMap",
                critical=False
            ),
            ServerConfig(
                name="GIS",
                module_path="src.mcp_servers.gis_server", 
                description="Análisis geoespacial avanzado con PostgreSQL/PostGIS",
                critical=False
            )
        ]
        
        logger.info("🏗️ ServerManager inicializado")
        
    def _validate_server_modules(self) -> List[ServerConfig]:
        """
        Validar que todos los módulos de servidores existen
        
        Returns:
            Lista de configuraciones de servidores válidos
            
        Raises:
            FileNotFoundError: Si algún módulo crítico no existe
        """
        valid_servers: List[ServerConfig] = []
        missing_critical: List[str] = []
        
        for config in self.server_configs:
            # Convertir ruta de módulo a ruta de archivo
            module_file_path = self.project_root / config.module_path.replace(".", "/") + ".py"
            
            if module_file_path.exists():
                valid_servers.append(config)
                logger.info(f"✅ Módulo encontrado: {config.module_path}")
            else:
                logger.warning(f"⚠️ Módulo no encontrado: {module_file_path}")
                if config.critical:
                    missing_critical.append(config.name)
        
        # Si faltan servidores críticos, detener la ejecución
        if missing_critical:
            error_msg = f"Servidores críticos no encontrados: {missing_critical}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
            
        return valid_servers
    
    def start_server(self, config: ServerConfig) -> bool:
        """
        Iniciar un servidor MCP individual
        
        Args:
            config: Configuración del servidor a iniciar
            
        Returns:
            True si el servidor se inició correctamente, False en caso contrario
        """
        try:
            logger.info(f"🚀 Iniciando servidor {config.name}...")
            logger.debug(f"   Módulo: {config.module_path}")
            logger.debug(f"   Descripción: {config.description}")
            
            # Crear proceso subprocess para el servidor usando -m
            process = subprocess.Popen(
                [sys.executable, "-m", config.module_path],
                stdout=subprocess.PIPE,  # Capturar stdout para logging
                stderr=subprocess.PIPE,  # Capturar stderr para debugging
                text=True,              # Usar strings en lugar de bytes
                bufsize=1,              # Buffering línea por línea
                universal_newlines=True,
                cwd=str(self.project_root)  # Ejecutar desde raíz del proyecto
            )
            
            # Verificar que el proceso se inició correctamente
            # Esperar un momento para detectar errores inmediatos
            time.sleep(0.5)
            
            if process.poll() is None:  # None significa que el proceso sigue ejecutándose
                self.processes[config.name] = process
                logger.info(f"✅ Servidor {config.name} iniciado correctamente (PID: {process.pid})")
                return True
            else:
                # El proceso terminó inmediatamente, probablemente un error
                stderr_output = process.stderr.read() if process.stderr else "No disponible"
                logger.error(f"❌ Servidor {config.name} falló al iniciar")
                logger.error(f"   Error: {stderr_output}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error iniciando servidor {config.name}: {e}")
            return False
    
    def stop_all_servers(self) -> None:
        """
        Detener todos los servidores de forma segura
        
        Implementa un cierre en dos fases:
        1. Terminación suave (SIGTERM) con timeout
        2. Terminación forzada (SIGKILL) si es necesario
        """
        if not self.processes:
            logger.info("ℹ️ No hay servidores activos para detener")
            return
            
        logger.info("🛑 Iniciando cierre de servidores...")
        
        # Fase 1: Terminación suave
        for name, process in self.processes.items():
            try:
                logger.info(f"🔄 Deteniendo servidor {name} (PID: {process.pid})...")
                process.terminate()  # Enviar SIGTERM
                
            except Exception as e:
                logger.error(f"⚠️ Error enviando SIGTERM a {name}: {e}")
        
        # Fase 2: Esperar terminación con timeout y forzar si es necesario
        timeout_seconds = 5
        for name, process in list(self.processes.items()):
            try:
                # Esperar que el proceso termine voluntariamente
                process.wait(timeout=timeout_seconds)
                logger.info(f"✅ Servidor {name} detenido correctamente")
                
            except subprocess.TimeoutExpired:
                # El proceso no terminó en el tiempo esperado, forzar cierre
                logger.warning(f"⚠️ Servidor {name} no respondió, forzando cierre...")
                try:
                    process.kill()  # Enviar SIGKILL
                    process.wait(timeout=2)
                    logger.info(f"🔨 Servidor {name} terminado forzadamente")
                except Exception as e:
                    logger.error(f"❌ Error forzando cierre de {name}: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Error deteniendo servidor {name}: {e}")
        
        # Limpiar el diccionario de procesos
        self.processes.clear()
        self.running = False
        logger.info("✅ Todos los servidores han sido detenidos")
    
    def signal_handler(self, signum: int, frame) -> None:
        """
        Manejador de señales del sistema (Ctrl+C, SIGTERM, etc.)
        
        Args:
            signum: Número de la señal recibida
            frame: Frame de ejecución actual (no usado)
        """
        signal_names = {
            signal.SIGINT: "SIGINT (Ctrl+C)",
            signal.SIGTERM: "SIGTERM",
            signal.SIGQUIT: "SIGQUIT"
        }
        
        signal_name = signal_names.get(signum, f"Señal {signum}")
        logger.info(f"📡 Señal recibida: {signal_name}")
        
        # Detener todos los servidores y salir
        self.stop_all_servers()
        logger.info("👋 Sistema detenido por señal del usuario")
        sys.exit(0)
    
    async def monitor_servers(self) -> None:
        """
        Monitorizar continuamente el estado de los servidores
        
        Funcionalidades:
        - Detecta servidores que han terminado inesperadamente
        - Registra logs de estado cada cierto tiempo
        - Permite restart automático (opcional, no implementado)
        """
        logger.info("🔍 Iniciando monitorización de servidores...")
        
        monitor_interval = 5  # segundos
        health_check_interval = 30  # segundos  
        last_health_check = time.time()
        
        while self.running:
            current_time = time.time()
            servers_alive = 0
            servers_dead = []
            
            # Verificar estado de cada servidor
            for name, process in list(self.processes.items()):
                return_code = process.poll()
                
                if return_code is None:
                    # Proceso sigue ejecutándose
                    servers_alive += 1
                else:
                    # Proceso ha terminado
                    servers_dead.append(name)
                    logger.error(f"💀 Servidor {name} ha terminado inesperadamente (código: {return_code})")
                    
                    # Leer stderr para diagnosticar el problema
                    try:
                        if process.stderr:
                            stderr_content = process.stderr.read()
                            if stderr_content:
                                logger.error(f"   Error de {name}: {stderr_content}")
                    except Exception:
                        pass  # No es crítico si no podemos leer stderr
                    
                    # Remover del diccionario de procesos activos
                    del self.processes[name]
            
            # Log de estado periódico
            if current_time - last_health_check >= health_check_interval:
                logger.info(f"📊 Estado del sistema: {servers_alive} servidores activos")
                last_health_check = current_time
            
            # Si todos los servidores han muerto, detener monitorización
            if not self.processes:
                logger.error("💥 Todos los servidores han terminado, deteniendo sistema")
                self.running = False
                break
            
            # Esperar antes de la siguiente verificación
            await asyncio.sleep(monitor_interval)
        
        logger.info("🔍 Monitorización de servidores finalizada")
    
    def display_startup_info(self) -> None:
        """
        Mostrar información de estado tras el inicio del sistema
        """
        print("\n" + "="*70)
        print("🎯 SISTEMA MCP RAG GIS v2.0 - ESTADO DE SERVIDORES")
        print("="*70)
        
        if self.processes:
            print(f"📋 Servidores activos ({len(self.processes)}):")
            for name, process in self.processes.items():
                config = next((c for c in self.server_configs if c.name == name), None)
                print(f"  ✅ {name:<8} (PID: {process.pid:<6}) - {config.description if config else 'N/A'}")
        else:
            print("❌ No hay servidores activos")
            return
        
        print("\n🔗 Endpoints disponibles:")
        print("  • Servidores MCP: Listos para conexión con Claude/IA")
        print("  • API REST: http://localhost:8000 (si está configurada)")
        print("  • Documentación: http://localhost:8000/docs")
        
        print(f"\n📝 Logs del sistema:")
        print(f"  • Nivel de log: {logging.getLogger().level}")
        print(f"  • Monitorización: Cada 5 segundos")
        
        print(f"\n⌨️  Controles:")
        print(f"  • Ctrl+C: Detener todos los servidores")
        print(f"  • Estado: Visible en logs cada 30 segundos")
        print("="*70 + "\n")
    
    def run(self) -> None:
        """
        Ejecutar el sistema completo de servidores MCP
        
        Flujo principal:
        1. Validar módulos de servidores
        2. Configurar manejadores de señales  
        3. Iniciar servidores secuencialmente
        4. Mostrar información de estado
        5. Iniciar monitorización continua
        """
        logger.info("🚀 Iniciando Sistema MCP RAG GIS v2.0")
        
        try:
            # Paso 1: Validar que todos los módulos existen
            valid_servers = self._validate_server_modules()
            logger.info(f"✅ Validación completada: {len(valid_servers)} servidores disponibles")
            
            # Paso 2: Configurar manejadores de señales para cierre limpio
            signal.signal(signal.SIGINT, self.signal_handler)   # Ctrl+C
            signal.signal(signal.SIGTERM, self.signal_handler)  # Terminación del proceso
            logger.info("🛡️ Manejadores de señales configurados")
            
            # Paso 3: Iniciar servidores secuencialmente
            successful_starts = 0
            for config in valid_servers:
                success = self.start_server(config)
                if success:
                    successful_starts += 1
                    # Pausa entre inicios para evitar conflictos de recursos
                    time.sleep(2)
                else:
                    if config.critical:
                        logger.error(f"❌ Servidor crítico {config.name} falló, deteniendo sistema")
                        self.stop_all_servers()
                        return
                    else:
                        logger.warning(f"⚠️ Servidor no crítico {config.name} falló, continuando...")
            
            # Verificar que al menos un servidor se inició
            if successful_starts == 0:
                logger.error("❌ No se pudo iniciar ningún servidor")
                return
            
            # Paso 4: Sistema iniciado correctamente
            self.running = True
            logger.info(f"🎉 Sistema iniciado: {successful_starts}/{len(valid_servers)} servidores activos")
            
            # Mostrar información de estado
            self.display_startup_info()
            
            # Paso 5: Iniciar monitorización continua (bloqueante)
            try:
                asyncio.run(self.monitor_servers())
            except KeyboardInterrupt:
                # Esta excepción normalmente la maneja signal_handler, 
                # pero por seguridad la capturamos aquí también
                logger.info("⌨️ Interrupción de teclado detectada")
                self.signal_handler(signal.SIGINT, None)
                
        except Exception as e:
            logger.error(f"💥 Error fatal en el sistema: {e}")
            self.stop_all_servers()
            raise
        
        finally:
            # Asegurar limpieza final
            if self.processes:
                logger.info("🧹 Limpieza final del sistema...")
                self.stop_all_servers()

def main() -> None:
    """
    Punto de entrada principal del script
    
    Crea una instancia del ServerManager y ejecuta el sistema
    """
    try:
        manager = ServerManager()
        manager.run()
    except KeyboardInterrupt:
        logger.info("👋 Sistema interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Error fatal no manejado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()