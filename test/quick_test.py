# quick_test.py
import asyncio
import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_rag_direct():
    """Probar RAG service directamente"""
    from services.rag_service import RAGService
    
    print("🧪 Probando RAGService directamente...")
    
    rag = RAGService()
    
    # Test info vectorstore
    info = await rag.get_vectorstore_info()
    print(f"📊 Info vectorstore: {info}")
    
    # Test lista documentos
    docs = await rag.list_documents("data/documents")
    print(f"📁 Documentos encontrados: {len(docs)}")

async def test_maps_direct():
    """Probar Maps service directamente"""
    from services.maps_service import MapsService
    
    print("\n🧪 Probando MapsService directamente...")
    
    maps = MapsService()
    
    # Test geocodificación
    try:
        lat, lon = await maps.geocode_address("Madrid, España")
        print(f"📍 Madrid geocodificado: {lat:.6f}, {lon:.6f}")
    except Exception as e:
        print(f"❌ Error geocodificación: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag_direct())
    asyncio.run(test_maps_direct())