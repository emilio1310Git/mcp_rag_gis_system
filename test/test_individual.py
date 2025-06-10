import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Testing config...")
from config import settings
print(f"✅ Config OK - DB: {settings.database.host}")

print("Testing RAG service...")
from services.rag_service import RAGService
print("✅ RAGService import OK")

print("Creating RAGService instance...")
rag = RAGService()
print("✅ RAGService instance OK")

print("🎉 All basic tests passed!")