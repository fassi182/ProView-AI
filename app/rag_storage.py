#app/rag_storage.py
import os
import time
import logging
from typing import List, Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.config import ProViewConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize embeddings (singleton pattern)
_embeddings_instance = None

def get_embeddings():
    """Lazy load embeddings to avoid multiple initializations"""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=ProViewConfig.EMBEDDING_MODEL
        )
    return _embeddings_instance

# Initialize vector database
vector_db = Chroma(
    collection_name="proview_prod", 
    embedding_function=get_embeddings(),
    persist_directory=ProViewConfig.PERSIST_DIRECTORY
)

def process_file(file_path: str, session_id: str) -> int:
    """
    Process uploaded file and store in vector database with session isolation
    
    Args:
        file_path: Path to the uploaded file
        session_id: Unique session identifier for data isolation
        
    Returns:
        Number of document chunks created
    """
    try:
        # Determine file type and select appropriate loader
        ext = os.path.splitext(file_path)[-1].lower()
        
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext == ".docx":
            loader = Docx2txtLoader(file_path)
        elif ext == ".txt":
            loader = TextLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # Load documents
        docs = loader.load()
        
        # Add metadata for session isolation and timestamp
        current_time = time.time()
        for doc in docs:
            doc.metadata["session_id"] = session_id
            doc.metadata["timestamp"] = current_time
            doc.metadata["source_file"] = os.path.basename(file_path)
        
        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700, 
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        splits = splitter.split_documents(docs)
        
        # Add to vector database
        if splits:
            vector_db.add_documents(splits)
            logger.info(f"Processed {len(splits)} chunks for session {session_id[:8]}...")
            return len(splits)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}")
        raise

def get_retrieved_context(query: str, session_id: str, k: int = 3) -> str:
    """
    Retrieve relevant context from vector database for a specific session
    
    Args:
        query: User's query string
        session_id: Session ID for data isolation
        k: Number of documents to retrieve
        
    Returns:
        Concatenated context string from retrieved documents
    """
    try:
        # Use metadata filter to ensure session isolation (CRITICAL for security)
        docs = vector_db.similarity_search(
            query, 
            k=k, 
            filter={"session_id": session_id}
        )
        
        if not docs:
            logger.info(f"No context found for session {session_id[:8]}...")
            return "No relevant context available. Please upload your resume or job description."
        
        # Combine document content
        context = "\n\n".join([doc.page_content for doc in docs])
        logger.info(f"Retrieved {len(docs)} documents for session {session_id[:8]}...")
        
        return context
        
    except Exception as e:
        logger.error(f"Error retrieving context: {str(e)}")
        return ""

def clear_session_data(session_id: str) -> int:
    """
    Clear all data for a specific session
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        Number of documents deleted
    """
    try:
        # Get all documents for this session
        results = vector_db.get(where={"session_id": session_id})
        
        if results and results.get('ids'):
            ids_to_delete = results['ids']
            vector_db.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} documents for session {session_id[:8]}...")
            return len(ids_to_delete)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {str(e)}")
        return 0

def janitor_cleanup(hours: Optional[float] = None) -> int:
    """
    Automatic cleanup of old session data
    
    Args:
        hours: Delete data older than this many hours (default from config)
        
    Returns:
        Number of documents deleted
    """
    if hours is None:
        hours = ProViewConfig.SESSION_TIMEOUT_HOURS
    
    try:
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        # Get all documents
        db_content = vector_db.get()
        
        if not db_content or not db_content.get('ids'):
            return 0
        
        # Find expired documents
        ids_to_delete = [
            db_content['ids'][i] 
            for i, metadata in enumerate(db_content.get('metadatas', []))
            if metadata.get('timestamp', 0) < cutoff_time
        ]
        
        # Delete expired documents
        if ids_to_delete:
            vector_db.delete(ids=ids_to_delete)
            logger.info(f"Janitor cleanup: Deleted {len(ids_to_delete)} expired documents")
            return len(ids_to_delete)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during janitor cleanup: {str(e)}")
        return 0

def get_session_stats(session_id: str) -> dict:
    """
    Get statistics about a session's stored data
    
    Args:
        session_id: Session ID to query
        
    Returns:
        Dictionary with session statistics
    """
    try:
        results = vector_db.get(where={"session_id": session_id})
        
        return {
            "document_count": len(results.get('ids', [])),
            "session_id": session_id,
            "has_data": len(results.get('ids', [])) > 0
        }
    except Exception as e:
        logger.error(f"Error getting session stats: {str(e)}")
        return {"document_count": 0, "session_id": session_id, "has_data": False}