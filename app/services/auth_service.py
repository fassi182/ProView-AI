import random
from datetime import datetime, timedelta, timezone
from app.database import supabase
from app.schemas import OTPVerify

class AuthService:
    
    @staticmethod
    def generate_six_digit_otp() -> str:
        """Generates a secure, random 6-digit numeric string."""
        return str(random.randint(100000, 999999))

    @classmethod
    def save_otp_to_cloud(cls, email: str) -> str:
        """
        Generates a fresh OTP, sets an expiration window of 5 minutes,
        and saves it directly into the cloud Supabase 'otps' table.
        """
        otp_code = cls.generate_six_digit_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        otp_data = {
            "email": email.strip().lower(),
            "otp_code": otp_code,
            "expires_at": expires_at.isoformat()
        }
        
        supabase.table("otps").insert(otp_data).execute()
        return otp_code

    @staticmethod
    def verify_otp_and_login(payload: OTPVerify) -> dict:
        """
        Validates the incoming email and OTP against cloud records.
        If valid, configures a customized profile interview session state.
        """
        email_clean = payload.email.strip().lower()
        current_time = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table("otps") \
            .select("*") \
            .eq("email", email_clean) \
            .eq("otp_code", payload.otp_code) \
            .gte("expires_at", current_time) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if not response.data:
            return {"status": "error", "message": "Invalid or expired OTP code."}
            
        # Ensure user profile exists
        user_check = supabase.table("users").select("*").eq("email", email_clean).execute()
        if not user_check.data:
            supabase.table("users").insert({"email": email_clean}).execute()
            message = "Registration successful! Welcome to ProView AI."
        else:
            message = "Login successful! Welcome back."
            
        # Clean up used OTP
        supabase.table("otps").delete().eq("email", email_clean).execute()
        
        # Extract configuration fields safely or apply fallbacks
        job_title = getattr(payload, "job_title", "AI/ML Engineer")
        difficulty = getattr(payload, "difficulty_level", "Medium")
        focus = getattr(payload, "interview_focus", "Mixed")
        
        # Insert a customized session record containing configuration profiles
        session_response = supabase.table("chat_sessions").insert({
            "user_email": email_clean,
            "job_title": job_title,
            "difficulty_level": difficulty,
            "interview_focus": focus
        }).execute()
        
        session_id = session_response.data[0]["session_id"] if session_response.data else None
        
        return {
            "status": "success", 
            "message": message, 
            "email": email_clean,
            "session_id": str(session_id)
        }