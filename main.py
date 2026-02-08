#main.py
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil
import os
import logging
from datetime import datetime
from typing import Optional
from collections import defaultdict
import time

from app.rag_storage import (
    process_file, 
    get_retrieved_context, 
    janitor_cleanup, 
    clear_session_data,
    get_session_stats
)
from app.services import get_proview_response
from app.schemas import ChatRequest, ChatResponse, UploadResponse, ClearResponse
from app.config import ProViewConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ProView AI - Interview Coach API",
    description="RAG-powered interview preparation system",
    version="1.0.0"
)

# CORS Configuration (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],  # Streamlit default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory rate limiting
rate_limit_store = defaultdict(list)

def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    current_time = time.time()
    window_start = current_time - ProViewConfig.RATE_LIMIT_WINDOW_SECONDS
    
    # Clean old requests
    rate_limit_store[client_ip] = [
        req_time for req_time in rate_limit_store[client_ip] 
        if req_time > window_start
    ]
    
    # Check limit
    if len(rate_limit_store[client_ip]) >= ProViewConfig.RATE_LIMIT_REQUESTS:
        return False
    
    # Add current request
    rate_limit_store[client_ip].append(current_time)
    return True

# Security: API Key validation
async def verify_api_key(x_proview_key: Optional[str] = Header(None)):
    """Verify the ProView API key"""
    if not x_proview_key or x_proview_key != ProViewConfig.PROVIEW_API_KEY:
        logger.warning(f"Unauthorized access attempt with key: {x_proview_key}")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-ProView-Key header"
        )
    return x_proview_key

# Startup event: Validate configuration
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    try:
        ProViewConfig.validate()
        logger.info("✅ ProView AI API started successfully")
        logger.info(f"📊 Model: {ProViewConfig.MODEL_NAME}")
        logger.info(f"🔒 Security: API Key authentication enabled")
        logger.info(f"⏰ Cleanup: {ProViewConfig.SESSION_TIMEOUT_HOURS} hour timeout")
    except Exception as e:
        logger.error(f"❌ Startup validation failed: {str(e)}")
        raise

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ProView AI Coach"
    }

# File upload endpoint
@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    api_key: str = Depends(verify_api_key),
    request: Request = None
):
    """
    Upload and process documents (resume, job description, etc.)
    """
    try:
        # Rate limiting
        client_ip = request.client.host if request else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
        
        # Validate file extension
        file_ext = os.path.splitext(file.filename)[-1].lower()
        if file_ext not in ProViewConfig.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {ProViewConfig.ALLOWED_EXTENSIONS}"
            )
        
        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size_mb = file.file.tell() / (1024 * 1024)
        file.file.seek(0)  # Reset
        
        if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {ProViewConfig.MAX_FILE_SIZE_MB}MB"
            )
        
        # Save temporarily
        temp_path = f"./temp_{session_id}_{file.filename}"
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Process file
            chunks_created = process_file(temp_path, session_id)
            
            logger.info(f"✅ Uploaded {file.filename} for session {session_id[:8]}... ({chunks_created} chunks)")
            
            return UploadResponse(
                status="success",
                message=f"Successfully processed {file.filename}",
                files_processed=1
            )
            
        finally:
            # Always cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    request: Request = None
):
    """
    Main chat endpoint for interview coaching
    """
    try:
        # Rate limiting
        client_ip = request.client.host if request else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
        
        # Schedule background cleanup
        background_tasks.add_task(janitor_cleanup)
        
        # Convert history format
        history = []
        for msg in data.history[-10:]:  # Keep last 10 messages
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
        
        logger.info(f"💬 Chat response for session {data.session_id[:8]}...")
        
        return ChatResponse(ai_response=ai_response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# Clear session endpoint
@app.post("/clear", response_model=ClearResponse)
async def clear_session(
    session_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Clear all data for a specific session
    """
    try:
        deleted_count = clear_session_data(session_id)
        
        logger.info(f"🧹 Cleared session {session_id[:8]}... ({deleted_count} documents)")
        
        return ClearResponse(
            status="success",
            message=f"Session data cleared successfully",
            documents_deleted=deleted_count
        )
        
    except Exception as e:
        logger.error(f"❌ Clear session error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")

# Session stats endpoint (useful for debugging)
@app.get("/session/{session_id}/stats")
async def get_stats(
    session_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get statistics about a session's stored data
    """
    try:
        stats = get_session_stats(session_id)
        return stats
    except Exception as e:
        logger.error(f"❌ Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

# Manual cleanup endpoint (admin use)
@app.post("/admin/cleanup")
async def manual_cleanup(
    hours: float = 2.0,
    api_key: str = Depends(verify_api_key)
):
    """
    Manually trigger cleanup of old data
    """
    try:
        deleted = janitor_cleanup(hours=hours)
        return {
            "status": "success",
            "message": f"Cleanup completed",
            "documents_deleted": deleted
        }
    except Exception as e:
        logger.error(f"❌ Cleanup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)