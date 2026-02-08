# app/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union
import re

class ProViewCoachOutput(BaseModel):
    """Structured output from the AI coach"""
    interviewer_chat: str = Field(..., description="Main conversation response from the AI coach")
    is_correct: Optional[bool] = Field(None, description="Whether the user's answer was correct")
    score: Optional[str] = Field(None, description="Score out of 10 in format 'X/10'")
    refined_explanation: Optional[str] = Field(None, description="Detailed feedback on the answer")
    suggested_replies: List[str] = Field(default_factory=list, description="Suggested follow-up responses")
    
    @field_validator('score')
    @classmethod
    def validate_score(cls, v: Optional[str]) -> Optional[str]:
        """Validate score format is 'X/10' where X is 0-10"""
        if v is None:
            return v
        
        # Check format with regex
        pattern = r'^(\d{1,2})/10$'
        match = re.match(pattern, v)
        
        if not match:
            raise ValueError("Score must be in format 'X/10' where X is a number")
        
        # Extract and validate the score value
        score_val = int(match.group(1))
        if not 0 <= score_val <= 10:
            raise ValueError("Score must be between 0 and 10")
        
        return v
    
    @field_validator('interviewer_chat')
    @classmethod
    def validate_interviewer_chat(cls, v: str) -> str:
        """Ensure interviewer_chat is not empty"""
        if not v or not v.strip():
            raise ValueError("interviewer_chat cannot be empty")
        return v.strip()

class MessageModel(BaseModel):
    """Chat message model for history"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: Union[str, dict]
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: Union[str, dict]) -> Union[str, dict]:
        """Validate content is not empty"""
        if isinstance(v, str) and not v.strip():
            raise ValueError("Message content cannot be empty")
        if isinstance(v, dict) and not v:
            raise ValueError("Message content dictionary cannot be empty")
        return v

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    session_id: str = Field(..., min_length=8, max_length=100)
    user_message: str = Field(..., min_length=1, max_length=5000)
    history: List[MessageModel] = Field(default_factory=list, max_length=50)
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Ensure session_id is alphanumeric with hyphens/underscores only"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("session_id must contain only alphanumeric characters, hyphens, and underscores")
        return v
    
    @field_validator('user_message')
    @classmethod
    def validate_user_message(cls, v: str) -> str:
        """Ensure message is not just whitespace"""
        if not v.strip():
            raise ValueError("user_message cannot be empty or whitespace")
        return v.strip()

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    ai_response: ProViewCoachOutput

class UploadResponse(BaseModel):
    """Response model for file upload"""
    status: str
    message: str
    files_processed: int = 0
    chunks_created: int = 0

class ClearResponse(BaseModel):
    """Response model for clearing session"""
    status: str
    message: str
    documents_deleted: int = 0

class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    error_type: str
    timestamp: str