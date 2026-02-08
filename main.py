# main.py
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import uuid

from app.rag_storage import (
    process_file, 
    get_retrieved_context, 
    janitor_cleanup, 
    clear_session_data,
    get_session_stats
)
from app.services import get_proview_response
from app.schemas import (
    ChatRequest, 
    ChatResponse, 
    UploadResponse, 
    ClearResponse,
    ErrorResponse
)
from app.config import ProViewConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with better metadata
app = FastAPI(
    title="ProView AI - Interview Coach API",
    description="RAG-powered interview preparation system with secure session management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration (from config)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ProViewConfig.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: API Key validation
async def verify_api_key(x_proview_key: Optional[str] = Header(None)):
    """Verify the ProView API key"""
    if not x_proview_key or x_proview_key != ProViewConfig.PROVIEW_API_KEY:
        logger.warning(f"Unauthorized access attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-ProView-Key header"
        )
    return x_proview_key

def get_client_ip(request: Request) -> str:
    """Extract client IP with proxy support"""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    return request.client.host if request.client else "unknown"

# Simple in-memory rate limiting (NOTE: Use Redis in production)
from collections import defaultdict
import time

rate_limit_store = defaultdict(list)

def check_rate_limit(client_ip: str) -> bool:
    """
    Check if client has exceeded rate limit
    
    NOTE: This is in-memory and will reset on server restart.
    For production, use Redis or similar persistent store.
    """
    current_time = time.time()
    window_start = current_time - ProViewConfig.RATE_LIMIT_WINDOW_SECONDS
    
    # Clean old requests
    rate_limit_store[client_ip] = [
        req_time for req_time in rate_limit_store[client_ip] 
        if req_time > window_start
    ]
    
    # Check limit
    if len(rate_limit_store[client_ip]) >= ProViewConfig.RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return False
    
    # Add current request
    rate_limit_store[client_ip].append(current_time)
    return True

def generate_safe_filename(session_id: str, original_filename: str) -> str:
    """
    Generate a safe, unique filename to prevent collisions
    
    Args:
        session_id: Session identifier
        original_filename: Original uploaded filename
        
    Returns:
        Safe filename with unique ID
    """
    # Extract extension
    ext = Path(original_filename).suffix.lower()
    
    # Generate unique ID
    unique_id = uuid.uuid4().hex[:8]
    
    # Create safe filename: session_uniqueid_timestamp.ext
    timestamp = int(time.time())
    safe_name = f"{session_id}_{unique_id}_{timestamp}{ext}"
    
    return safe_name

# Startup event: Validate configuration
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    try:
        ProViewConfig.validate()
        logger.info("=" * 60)
        logger.info("✅ ProView AI API started successfully")
        logger.info(f"📊 Model: {ProViewConfig.MODEL_NAME}")
        logger.info(f"🔒 Security: API Key authentication enabled")
        logger.info(f"⏰ Cleanup: {ProViewConfig.SESSION_TIMEOUT_HOURS} hour timeout")
        logger.info(f"📁 Max file size: {ProViewConfig.MAX_FILE_SIZE_MB}MB")
        logger.info(f"🌐 CORS origins: {ProViewConfig.ALLOWED_ORIGINS}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ Startup validation failed: {str(e)}")
        raise

# Shutdown event: Cleanup
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("🛑 ProView AI API shutting down...")
    # Perform any necessary cleanup
    logger.info("✅ Shutdown complete")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ProView AI Coach",
        "version": "1.0.0"
    }

# File upload endpoint with improved security
@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    api_key: str = Depends(verify_api_key),
    request: Request = None
):
    """
    Upload and process documents (resume, job description, etc.)
    
    Security features:
    - Rate limiting
    - File type validation
    - File size limits (before full upload)
    - Safe filename generation
    - Proper cleanup on error
    """
    temp_path = None
    
    try:
        # Rate limiting
        client_ip = get_client_ip(request) if request else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Too many requests. Please wait before uploading again."
            )
        
        # Validate file has a filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ProViewConfig.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(ProViewConfig.ALLOWED_EXTENSIONS)}"
            )
        
        # Validate file size BEFORE reading entire file
        # Note: This uses content-length header if available
        content_length = request.headers.get('content-length')
        if content_length:
            file_size_mb = int(content_length) / (1024 * 1024)
            if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large ({file_size_mb:.2f}MB). Maximum size: {ProViewConfig.MAX_FILE_SIZE_MB}MB"
                )
        
        # Generate safe filename to prevent collisions
        safe_filename = generate_safe_filename(session_id, file.filename)
        temp_path = os.path.join(ProViewConfig.TEMP_UPLOAD_DIR, safe_filename)
        
        # Ensure temp directory exists
        os.makedirs(ProViewConfig.TEMP_UPLOAD_DIR, exist_ok=True)
        
        # Save file with size validation
        total_size = 0
        max_size_bytes = ProViewConfig.MAX_FILE_SIZE_MB * 1024 * 1024
        
        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                total_size += len(chunk)
                if total_size > max_size_bytes:
                    # Remove partial file
                    buffer.close()
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {ProViewConfig.MAX_FILE_SIZE_MB}MB"
                    )
                buffer.write(chunk)
        
        # Process file
        chunks_created = process_file(temp_path, session_id)
        
        logger.info(f"✅ Uploaded '{file.filename}' for session {session_id[:8]}... ({chunks_created} chunks, {total_size/1024:.2f}KB)")
        
        return UploadResponse(
            status="success",
            message=f"Successfully processed '{file.filename}'",
            files_processed=1,
            chunks_created=chunks_created
        )
        
    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Validation error during upload: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        # Always cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup temp file {temp_path}: {str(e)}")

# Chat endpoint with improved error handling
@app.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    request: Request = None
):
    """
    Main chat endpoint for interview coaching
    
    Features:
    - Rate limiting
    - History length management
    - Background cleanup
    - Structured error handling
    """
    try:
        # Rate limiting
        client_ip = get_client_ip(request) if request else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Too many requests. Please wait before sending another message."
            )
        
        # Schedule background cleanup (non-blocking)
        background_tasks.add_task(janitor_cleanup)
        
        # Limit history length to prevent context overflow
        history = []
        for msg in data.history[-ProViewConfig.MAX_HISTORY_LENGTH:]:
            history.append({
                "role": msg.role,
                "content": msg.content if isinstance(msg.content, str) else msg.content
            })
        
        # Generate AI response
        ai_response = get_proview_response(
            user_input=data.user_message,
            chat_history=history,
            session_id=data.session_id
        )
        
        logger.info(f"💬 Chat response generated for session {data.session_id[:8]}...")
        
        return ChatResponse(ai_response=ai_response)
        
    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Validation error in chat: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your message. Please try again.")

# Clear session endpoint
@app.post("/clear", response_model=ClearResponse)
async def clear_session(
    session_id: str = Form(...),
    api_key: str = Depends(verify_api_key)
):
    """
    Clear all data for a specific session
    
    This removes all uploaded documents and embeddings for the given session.
    """
    try:
        if not session_id or len(session_id) < 8:
            raise HTTPException(status_code=400, detail="Invalid session_id")
        
        deleted_count = clear_session_data(session_id)
        
        logger.info(f"🧹 Cleared session {session_id[:8]}... ({deleted_count} documents)")
        
        return ClearResponse(
            status="success",
            message=f"Session data cleared successfully",
            documents_deleted=deleted_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Clear session error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")

# Session stats endpoint (useful for debugging and UI)
@app.get("/session/{session_id}/stats")
async def get_stats(
    session_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get statistics about a session's stored data
    
    Returns information about uploaded files and document chunks.
    """
    try:
        if not session_id or len(session_id) < 8:
            raise HTTPException(status_code=400, detail="Invalid session_id")
        
        stats = get_session_stats(session_id)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stats error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# Manual cleanup endpoint (admin use)
@app.post("/admin/cleanup")
async def manual_cleanup(
    hours: float = Form(default=2.0),
    api_key: str = Depends(verify_api_key)
):
    """
    Manually trigger cleanup of old data
    
    Removes all session data older than the specified number of hours.
    """
    try:
        if hours <= 0:
            raise HTTPException(status_code=400, detail="Hours must be positive")
        
        deleted = janitor_cleanup(hours=hours)
        
        logger.info(f"🧹 Manual cleanup completed: {deleted} documents deleted (cutoff: {hours}h)")
        
        return {
            "status": "success",
            "message": f"Cleanup completed",
            "documents_deleted": deleted,
            "cutoff_hours": hours
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Cleanup error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "error_type": type(exc).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

# 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": f"Endpoint not found: {request.url.path}",
            "available_endpoints": [
                "/health",
                "/upload",
                "/chat",
                "/clear",
                "/session/{session_id}/stats",
                "/docs"
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )