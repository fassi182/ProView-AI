#app/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union

class ProViewCoachOutput(BaseModel):
    """Structured output from the AI coach"""
    interviewer_chat: str = Field(..., description="Main conversation response from the AI coach")
    is_correct: Optional[bool] = Field(None, description="Whether the user's answer was correct")
    score: Optional[str] = Field(None, description="Score out of 10")
    refined_explanation: Optional[str] = Field(None, description="Detailed feedback on the answer")
    suggested_replies: List[str] = Field(default_factory=list, description="Suggested follow-up responses")
    
    @field_validator('score')
    @classmethod
    def validate_score(cls, v):
        if v is not None and not v.isdigit():
            try:
                score_val = int(v.split('/')[0])
                if not 0 <= score_val <= 10:
                    raise ValueError("Score must be between 0 and 10")
            except:
                pass
        return v

class MessageModel(BaseModel):
    """Chat message model for history"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: Union[str, dict]

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    session_id: str = Field(..., min_length=8, max_length=100)
    user_message: str = Field(..., min_length=1, max_length=5000)
    history: List[MessageModel] = Field(default_factory=list, max_length=50)

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    ai_response: ProViewCoachOutput

class UploadResponse(BaseModel):
    """Response model for file upload"""
    status: str
    message: str
    files_processed: int = 0

class ClearResponse(BaseModel):
    """Response model for clearing session"""
    status: str
    message: str
    documents_deleted: int = 0