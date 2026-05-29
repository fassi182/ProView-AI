from pydantic import BaseModel, Field
from typing import List, Optional

class OTPRequest(BaseModel):
    email: str = Field(..., example="user@example.com")

class OTPVerify(BaseModel):
    email: str = Field(..., example="user@example.com")
    otp_code: str = Field(..., example="123456")
    
    # Optional parameters enabling configuration setups immediately at entry handshake
    job_title: Optional[str] = Field(default="AI/ML Engineer", example="Hybrid AI/ML Engineer")
    difficulty_level: Optional[str] = Field(default="Medium", example="Hard")
    interview_focus: Optional[str] = Field(default="Mixed", example="Technical")

class AuthResponse(BaseModel):
    status: str = Field(..., example="success")
    message: str = Field(..., example="Login successful!")
    email: str = Field(..., example="user@example.com")
    session_id: Optional[str] = Field(None, example="eff42fed-8bbe-4dff-ae0b-38e78c1b0ce5")

class MessageModel(BaseModel):
    role: str = Field(..., example="user")
    content: str = Field(..., example="Your message goes here.")

class ProViewCoachOutput(BaseModel):
    interviewer_chat: str = Field(..., description="The next interview question or statement from the AI coach.")
    score: Optional[str] = Field(None, description="A score evaluation out of 10 for the user's performance.")
    refined_explanation: Optional[str] = Field(None, description="Detailed actionable analysis on how to improve the response.")
    suggested_replies: List[str] = Field(default=[], description="Actionable suggestion chips for the frontend dashboard interface.")

class ChatResponse(BaseModel):
    ai_response: ProViewCoachOutput