from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.services.rag_service import RagService

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["RAG Knowledge Ingestion Engine"]
)

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_interview_context_document(
    email: str = Form(..., description="The user email tracking ownership of this context file"),
    file: UploadFile = File(..., description="The PDF CV, Resume, or Job Description document")
):
    """
    Accepts raw PDF uploads, reads text elements, vectors data points 
    via Groq Embeddings, and inserts them directly to Supabase cloud tables.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file layout format. Only standard PDF formats are accepted."
        )

    try:
        # Read file text bytes directly out of incoming API stream memory buffer
        contents = await file.read()
        
        chunks_count = RagService.process_and_store_pdf(
            file_bytes=contents,
            filename=file.filename,
            user_email=email
        )

        return {
            "status": "success",
            "message": f"Document '{file.filename}' processed successfully.",
            "chunks_ingested": chunks_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing pipeline failed: {str(e)}"
        )