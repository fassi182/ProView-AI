from fastapi import APIRouter, HTTPException, status
from app.schemas import OTPRequest, OTPVerify, AuthResponse
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["User Security & Session Management"]
)

@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp(payload: OTPRequest):
    """
    Accepts a user email address and generates a short-lived 6-digit verification code.
    Dispatches the code cleanly directly to terminal execution logs.
    """
    try:
        otp_code = AuthService.save_otp_to_cloud(payload.email)
        
        # Security log simulator mimicking automated transactional dispatch channels
        print("\n==================================================")
        print(f" PROVIEW AI SECURITY LOG RECONCILIATION LAYER")
        print(f" TARGET DESTINATION: {payload.email.strip().lower()}")
        print(f" GENERATED DISPATCH PASSCODE: [ {otp_code} ]")
        print("==================================================\n")
        
        return {
            "status": "success",
            "message": "Verification code dispatched to terminal logs."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security engine failed to cache validation token: {str(e)}"
        )


@router.post("/verify-otp", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def verify_otp(payload: OTPVerify):
    """
    Validates incoming passcode claims. On success, configures isolated profile 
    configurations and generates a stateful session key template mapping.
    """
    try:
        result = AuthService.verify_otp_and_login(payload)
        
        # Guardrail: check if authentication verification returned an explicit error
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.get("message", "Authentication challenge verification failed.")
            )
            
        # Safely extract and parse variables into AuthResponse on confirmation success
        return AuthResponse(
            status=result.get("status", "success"),
            message=result.get("message", "Login successful."),
            email=result.get("email"),
            session_id=result.get("session_id")
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security clearing processing failure: {str(e)}"
        )