"""Servicio RAG actualizado con LangChain 0.3+"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# LangChain actualizado
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA

from ..config import settings
from ..utils.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

class RAGService:
    """Servicio RAG mejorado con LangChain 0.3+"""
    
    def __init__(self):
        self.embeddings = None
        self.llm = None
        self.vectorstore = None
        self.retrieval_chain = None
        self.document_processor = DocumentProcessor()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
    async def initialize(self):
        """Inicializar componentes del servicio RAG"""
        try:
            # Inicializar embeddings con la nueva API
            self.embeddings = OllamaEmbeddings(
                model=settings.ollama.embedding_model,
                base_url=settings.ollama.url
            )
            
            # Inicializar LLM con la nueva API
            self.llm = OllamaLLM(
                model=settings.ollama.default_model,
                base_url=settings.ollama.url,
                temperature=settings.ollama.temperature,
                top_p=settings.ollama.top_p,
                num_predict=settings.ollama.max_tokens
            )
            
            # Cargar vectorstore si existe
            self._load_existing_vectorstore()
            
            logger.info("Servicio RAG inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando servicio RAG: {e}")
            raise
    
    async def _load_existing_vectorstore(self):
        """Cargar vectorstore existente si está disponible"""
        vectorstore_path = settings.paths.vector_db_dir
        
        if vectorstore_path.exists() and any(vectorstore_path.iterdir()):
            try:
                self.vectorstore = Chroma(
                    persist_directory=str(vectorstore_path),
                    embedding_function=self.embeddings
                )
                
                # Configurar cadena de retrieval
                await self._setup_retrieval_chain()
                
                logger.info("Vectorstore existente cargado correctamente")
                
            except Exception as e:
                logger.warning(f"No se pudo cargar vectorstore existente: {e}")
                self.vectorstore = None
    
    async def _setup_retrieval_chain(self):
        """Configurar cadena de retrieval con la nueva API"""
        if not self.vectorstore:
            logger.warning("No hay vectorstore disponible para configurar retrieval")
            return
        
        try:
            # Crear retriever
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": settings.rag.similarity_search_k}
            )
            
            # Template de prompt mejorado
            prompt_template = """Eres un asistente experto en análisis de documentos y datos geoespaciales. 
            Usa el siguiente contexto para responder la pregunta de manera precisa y detallada.

            Contexto:
            {context}

            Pregunta: {question}

            Instrucciones:
            - Responde basándote únicamente en el contexto proporcionado
            - Si no tienes información suficiente, indícalo claramente
            - Incluye detalles específicos cuando sea relevante
            - Menciona las fuentes cuando sea apropiado

            Respuesta:"""
            
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            # Función para formatear documentos
            def format_docs(docs):
                return "\n\n".join([
                    f"Fuente: {doc.metadata.get('source', 'desconocida')}\n{doc.page_content}"
                    for doc in docs
                ])
            
            # Crear cadena con la nueva API
            self.retrieval_chain = (
                {
                    "context": retriever | format_docs,
                    "question": RunnablePassthrough()
                }
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            logger.info("Cadena de retrieval configurada correctamente")
            
        except Exception as e:
            logger.error(f"Error configurando cadena de retrieval: {e}")
            raise
    
    async def process_documents(self, documents_path: str) -> List[Document]:
        """Procesar documentos y crear chunks"""
        try:
            documents_dir = Path(documents_path)
            
            if not documents_dir.exists():
                raise ValueError(f"El directorio {documents_path} no existe")
            
            all_documents = []
            
            # Procesar archivos por tipo
            for file_path in documents_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in settings.rag.supported_extensions:
                    try:
                        # Procesar según el tipo de archivo
                        content = await self.document_processor.process_file(file_path)
                        
                        if content:
                            # Crear chunks del contenido
                            chunks = self.text_splitter.split_text(content)
                            
                            for i, chunk in enumerate(chunks):
                                doc = Document(
                                    page_content=chunk,
                                    metadata={
                                        "source": str(file_path),
                                        "chunk_id": i,
                                        "file_type": file_path.suffix,
                                        "file_name": file_path.name,
                                        "chunk_size": len(chunk)
                                    }
                                )
                                all_documents.append(doc)
                            
                            logger.info(f"Procesado: {file_path} ({len(chunks)} chunks)")
                    
                    except Exception as e:
                        logger.error(f"Error procesando {file_path}: {e}")
                        continue
            
            logger.info(f"Total de documentos procesados: {len(all_documents)}")
            return all_documents
            
        except Exception as e:
            logger.error(f"Error en process_documents: {e}")
            raise
    
    async def create_vectorstore(self, documents: List[Document]) -> bool:
        """Crear nueva base de datos vectorial"""
        if not documents:
            logger.warning("No hay documentos para crear vectorstore")
            return False
        
        try:
            # Crear nuevo vectorstore
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=str(settings.paths.vector_db_dir)
            )
            
            # Configurar cadena de retrieval
            await self._setup_retrieval_chain()
            
            logger.info(f"Vectorstore creado con {len(documents)} documentos")
            return True
            
        except Exception as e:
            logger.error(f"Error creando vectorstore: {e}")
            raise
    
    async def add_documents(self, documents: List[Document]) -> bool:
        """Añadir documentos al vectorstore existente"""
        if not self.vectorstore:
            logger.error("No hay vectorstore inicializado")
            return False
        
        if not documents:
            logger.warning("No hay documentos para añadir")
            return False
        
        try:
            # Añadir documentos al vectorstore existente
            self.vectorstore.add_documents(documents)
            
            logger.info(f"Añadidos {len(documents)} documentos al vectorstore")
            return True
            
        except Exception as e:
            logger.error(f"Error añadiendo documentos: {e}")
            raise
    
    async def query(self, question: str) -> Dict[str, Any]:
        """Realizar consulta RAG"""
        if not self.retrieval_chain:
            return {
                "error": "Sistema RAG no configurado. Procesa documentos primero.",
                "answer": "",
                "sources": []
            }
        
        try:
            # Realizar búsqueda de documentos relevantes
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": settings.rag.similarity_search_k}
            )
            relevant_docs = await retriever.ainvoke(question)
            
            # Generar respuesta usando la cadena
            answer = await self.retrieval_chain.ainvoke(question)
            
            # Preparar metadatos de fuentes
            sources = []
            for doc in relevant_docs:
                source_info = {
                    "source": doc.metadata.get("source", "desconocida"),
                    "file_name": doc.metadata.get("file_name", ""),
                    "chunk_id": doc.metadata.get("chunk_id", 0),
                    "file_type": doc.metadata.get("file_type", ""),
                    "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                }
                sources.append(source_info)
            
            return {
                "answer": answer,
                "sources": sources,
                "num_sources": len(sources)
            }
            
        except Exception as e:
            logger.error(f"Error en consulta RAG: {e}")
            return {
                "error": f"Error procesando consulta: {str(e)}",
                "answer": "",
                "sources": []
            }
    
    async def get_vectorstore_info(self) -> Dict[str, Any]:
        """Obtener información del vectorstore"""
        if not self.vectorstore:
            return {"status": "no_initialized", "document_count": 0}
        
        try:
            # Obtener estadísticas básicas
            collection = self.vectorstore._collection
            count = collection.count()
            
            return {
                "status": "ready",
                "document_count": count,
                "embedding_model": settings.ollama.embedding_model,
                "llm_model": settings.ollama.default_model,
                "vectorstore_path": str(settings.paths.vector_db_dir)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo info del vectorstore: {e}")
            return {"status": "error", "error": str(e)}
    
    async def list_documents(self, path: str) -> List[Dict[str, Any]]:
        """Listar documentos disponibles en un directorio"""
        try:
            documents_dir = Path(path)
            
            if not documents_dir.exists():
                return []
            
            documents = []
            for file_path in documents_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in settings.rag.supported_extensions:
                    file_info = {
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix,
                        "modified": file_path.stat().st_mtime
                    }
                    documents.append(file_info)
            
            return sorted(documents, key=lambda x: x["modified"], reverse=True)
            
        except Exception as e:
            logger.error(f"Error listando documentos: {e}")
            return []