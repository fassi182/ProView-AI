# app/rag_storage.py
import os
import time
import logging
from typing import List, Optional
from pathlib import Path
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
_vector_db_instance = None

def get_embeddings():
    """Lazy load embeddings to avoid multiple initializations"""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=ProViewConfig.EMBEDDING_MODEL
        )
    return _embeddings_instance

def get_vector_db():
    """Lazy load vector database"""
    global _vector_db_instance
    if _vector_db_instance is None:
        _vector_db_instance = Chroma(
            collection_name="proview_prod", 
            embedding_function=get_embeddings(),
            persist_directory=ProViewConfig.PERSIST_DIRECTORY
        )
    return _vector_db_instance

def validate_file_path(file_path: str) -> Path:
    """
    Validate and sanitize file path to prevent path traversal attacks
    
    Args:
        file_path: Path to validate
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If path is invalid or potentially malicious
    """
    try:
        # Convert to absolute path
        abs_path = Path(file_path).resolve()
        
        # Ensure file exists
        if not abs_path.exists():
            raise ValueError(f"File does not exist: {file_path}")
        
        # Ensure it's a file, not a directory
        if not abs_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Check file size
        file_size_mb = abs_path.stat().st_size / (1024 * 1024)
        if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
            raise ValueError(f"File exceeds maximum size of {ProViewConfig.MAX_FILE_SIZE_MB}MB")
        
        return abs_path
        
    except Exception as e:
        logger.error(f"Path validation failed: {str(e)}")
        raise ValueError(f"Invalid file path: {str(e)}")

def process_file(file_path: str, session_id: str) -> int:
    """
    Process uploaded file and store in vector database with session isolation
    
    Args:
        file_path: Path to the uploaded file
        session_id: Unique session identifier for data isolation
        
    Returns:
        Number of document chunks created
        
    Raises:
        ValueError: If file type is unsupported or validation fails
        Exception: If processing fails
    """
    docs = None
    splits = None
    
    try:
        # Validate file path (security)
        validated_path = validate_file_path(file_path)
        
        # Determine file type and select appropriate loader
        ext = validated_path.suffix.lower()
        
        if ext == ".pdf":
            loader = PyPDFLoader(str(validated_path))
        elif ext == ".docx":
            loader = Docx2txtLoader(str(validated_path))
        elif ext == ".txt":
            loader = TextLoader(str(validated_path), encoding='utf-8')
        else:
            raise ValueError(f"Unsupported file type: {ext}. Allowed: {ProViewConfig.ALLOWED_EXTENSIONS}")
        
        # Load documents
        logger.info(f"Loading file: {validated_path.name}")
        docs = loader.load()
        
        if not docs:
            raise ValueError("No content could be extracted from the file")
        
        # Add metadata for session isolation and timestamp
        current_time = time.time()
        for doc in docs:
            doc.metadata["session_id"] = session_id
            doc.metadata["timestamp"] = current_time
            doc.metadata["source_file"] = validated_path.name
        
        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700, 
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        splits = splitter.split_documents(docs)
        
        if not splits:
            raise ValueError("Document splitting produced no chunks")
        
        # Add to vector database
        vector_db = get_vector_db()
        vector_db.add_documents(splits)
        
        logger.info(f"✅ Processed {len(splits)} chunks for session {session_id[:8]}... from {validated_path.name}")
        return len(splits)
        
    except ValueError as ve:
        logger.error(f"Validation error processing file: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to process file: {str(e)}")
    finally:
        # Cleanup memory
        del docs
        del splits

def get_retrieved_context(query: str, session_id: str, k: int = 3) -> str:
    """
    Retrieve relevant context from vector database for a specific session
    
    Args:
        query: User's query string
        session_id: Session ID for data isolation
        k: Number of documents to retrieve (max 10)
        
    Returns:
        Concatenated context string from retrieved documents
    """
    try:
        # Validate inputs
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return "No query provided."
        
        if k < 1 or k > 10:
            logger.warning(f"Invalid k value: {k}, using default 3")
            k = 3
        
        # Use metadata filter to ensure session isolation (CRITICAL for security)
        vector_db = get_vector_db()
        docs = vector_db.similarity_search(
            query.strip(), 
            k=k, 
            filter={"session_id": session_id}
        )
        
        if not docs:
            logger.info(f"No context found for session {session_id[:8]}...")
            return "No relevant context available. Please upload your resume or job description to get personalized interview questions."
        
        # Combine document content with source attribution
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get('source_file', 'unknown')
            content = doc.page_content.strip()
            context_parts.append(f"[Source {i}: {source}]\n{content}")
        
        context = "\n\n---\n\n".join(context_parts)
        logger.info(f"Retrieved {len(docs)} documents for session {session_id[:8]}...")
        
        return context
        
    except Exception as e:
        logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
        return "Error retrieving context. Please try again."

def clear_session_data(session_id: str) -> int:
    """
    Clear all data for a specific session
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        Number of documents deleted
    """
    try:
        # Validate session_id
        if not session_id or not session_id.strip():
            logger.error("Invalid session_id provided for clearing")
            return 0
        
        vector_db = get_vector_db()
        
        # Get all documents for this session
        results = vector_db.get(where={"session_id": session_id})
        
        if results and results.get('ids'):
            ids_to_delete = results['ids']
            vector_db.delete(ids=ids_to_delete)
            logger.info(f"🧹 Deleted {len(ids_to_delete)} documents for session {session_id[:8]}...")
            return len(ids_to_delete)
        
        logger.info(f"No documents found for session {session_id[:8]}...")
        return 0
        
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {str(e)}", exc_info=True)
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
        
        vector_db = get_vector_db()
        
        # Get all documents
        db_content = vector_db.get()
        
        if not db_content or not db_content.get('ids'):
            logger.info("No documents in database for cleanup")
            return 0
        
        # Find expired documents
        ids_to_delete = []
        for i, metadata in enumerate(db_content.get('metadatas', [])):
            timestamp = metadata.get('timestamp', 0)
            if timestamp < cutoff_time:
                ids_to_delete.append(db_content['ids'][i])
        
        # Delete expired documents
        if ids_to_delete:
            vector_db.delete(ids=ids_to_delete)
            logger.info(f"🧹 Janitor cleanup: Deleted {len(ids_to_delete)} expired documents (older than {hours}h)")
            return len(ids_to_delete)
        
        logger.info(f"Janitor cleanup: No expired documents found (cutoff: {hours}h)")
        return 0
        
    except Exception as e:
        logger.error(f"Error during janitor cleanup: {str(e)}", exc_info=True)
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
        if not session_id or not session_id.strip():
            return {"error": "Invalid session_id", "document_count": 0, "has_data": False}
        
        vector_db = get_vector_db()
        results = vector_db.get(where={"session_id": session_id})
        
        doc_count = len(results.get('ids', []))
        
        # Get unique source files
        source_files = set()
        for metadata in results.get('metadatas', []):
            if 'source_file' in metadata:
                source_files.add(metadata['source_file'])
        
        return {
            "document_count": doc_count,
            "session_id": session_id,
            "has_data": doc_count > 0,
            "source_files": list(source_files),
            "file_count": len(source_files)
        }
    except Exception as e:
        logger.error(f"Error getting session stats: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "document_count": 0,
            "session_id": session_id,
            "has_data": False
        }