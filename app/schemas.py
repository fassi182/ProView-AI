##app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ProViewCoachOutput(BaseModel):
    interviewer_chat: str = Field(...)

    score: Optional[str] = None
    refined_explanation: Optional[str] = None
    suggested_replies: List[str] = []

class MessageModel(BaseModel):
    role: str
    content: str

class ChatResponse(BaseModel):
    ai_response: ProViewCoachOutput