from fastapi import APIRouter, HTTPException, status
from app.database import supabase

router = APIRouter(
    prefix="/api/v1/history",
    tags=["Session History Retrieval Engine"]
)

@router.get("/sessions", status_code=status.HTTP_200_OK)
async def get_user_interview_sessions(email: str):
    """
    Retrieves all past interview sessions for a specific user email.
    Useful for building the dashboard history list component on the frontend.
    """
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email parameter is required to isolate session history."
        )
        
    try:
        # Query the cloud chat_sessions ledger, ordering by newest session first
        response = supabase.table("chat_sessions") \
            .select("session_id", "created_at", "user_email") \
            .eq("user_email", email.strip().lower()) \
            .order("created_at", desc=True) \
            .execute()
            
        return {
            "status": "success",
            "count": len(response.data) if response.data else 0,
            "sessions": response.data if response.data else []
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch historical session ledger: {str(e)}"
        )


@router.get("/session/{session_id}/messages", status_code=status.HTTP_200_OK)
async def get_session_chat_transcript(session_id: str):
    """
    Retrieves the complete question-and-answer transcript for a specific session ID.
    Loads old conversational turns when a user clicks on a past interview card.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid session UUID is required to map message transcripts."
        )
        
    try:
        # Check if the session reference exists first
        session_check = supabase.table("chat_sessions") \
            .select("session_id") \
            .eq("session_id", session_id) \
            .limit(1) \
            .execute()
            
        if not session_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested interview session ID does not exist."
            )

        # FIX: Removed 'id' from the select statement to avoid schema cache conflicts
        messages_response = supabase.table("chat_messages") \
            .select("role", "interviewer_chat", "score", "suggested_replies", "created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()
            
        return {
            "status": "success",
            "session_id": session_id,
            "transcript_count": len(messages_response.data) if messages_response.data else 0,
            "messages": messages_response.data if messages_response.data else []
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve message thread execution trace: {str(e)}"
        )