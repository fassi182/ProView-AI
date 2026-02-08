# streamlit_app.py
"""
ProView AI Interview Coach - Streamlit GUI

This app works in two modes:
1. LOCAL MODE: Imports functions directly from app modules
2. DEPLOYED MODE: Calls FastAPI endpoints using environment variables

Mode is automatically detected based on environment.
"""

import streamlit as st
import os
import uuid
import time
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

# ============================================================================
# CONFIGURATION & MODE DETECTION
# ============================================================================

class AppConfig:
    """Configuration for the Streamlit app"""
    
    # Detect deployment mode
    IS_DEPLOYED = os.getenv("STREAMLIT_DEPLOYED", "false").lower() == "true"
    
    # API Configuration (for deployed mode)
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    API_KEY = os.getenv("PROVIEW_API_KEY", "default-secret-key-change-me")
    
    # App Settings
    APP_TITLE = "ProView AI Interview Coach"
    APP_ICON = "🎯"
    MAX_FILE_SIZE_MB = 10
    ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"]
    
    # UI Settings
    SHOW_DEBUG = os.getenv("SHOW_DEBUG", "false").lower() == "true"

# ============================================================================
# LOCAL MODE IMPORTS (only when running locally)
# ============================================================================

if not AppConfig.IS_DEPLOYED:
    try:
        # Import local modules
        from app.services import get_proview_response
        from app.rag_storage import process_file, clear_session_data, get_session_stats
        from app.schemas import ProViewCoachOutput
        
        LOCAL_MODE_AVAILABLE = True
        print("✅ Running in LOCAL MODE - Using direct imports")
    except ImportError as e:
        LOCAL_MODE_AVAILABLE = False
        print(f"⚠️ Local imports failed: {e}")
        print("Falling back to API mode")
else:
    LOCAL_MODE_AVAILABLE = False
    print("✅ Running in DEPLOYED MODE - Using API calls")

# ============================================================================
# API CLIENT (for deployed mode)
# ============================================================================

class ProViewAPIClient:
    """Client for interacting with ProView API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "X-ProView-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def upload_file(self, file_path: str, session_id: str) -> Dict[str, Any]:
        """Upload a file to the API"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {'session_id': session_id}
                headers = {"X-ProView-Key": self.api_key}
                
                response = requests.post(
                    f"{self.base_url}/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Upload failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def chat(self, user_message: str, history: List[Dict], session_id: str) -> Dict[str, Any]:
        """Send a chat message to the API"""
        try:
            payload = {
                "session_id": session_id,
                "user_message": user_message,
                "history": history
            }
            
            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                headers=self.headers,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Chat request failed: {str(e)}")
            return {
                "ai_response": {
                    "interviewer_chat": f"Error: {str(e)}",
                    "suggested_replies": []
                }
            }
    
    def clear_session(self, session_id: str) -> Dict[str, Any]:
        """Clear session data"""
        try:
            headers = {"X-ProView-Key": self.api_key}
            data = {"session_id": session_id}
            
            response = requests.post(
                f"{self.base_url}/clear",
                data=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Clear session failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get session statistics"""
        try:
            response = requests.get(
                f"{self.base_url}/session/{session_id}/stats",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"has_data": False, "document_count": 0}

# ============================================================================
# UNIFIED SERVICE LAYER
# ============================================================================

class ProViewService:
    """Unified service that works in both local and deployed modes"""
    
    def __init__(self):
        self.mode = "LOCAL" if (not AppConfig.IS_DEPLOYED and LOCAL_MODE_AVAILABLE) else "API"
        
        if self.mode == "API":
            self.api_client = ProViewAPIClient(AppConfig.API_BASE_URL, AppConfig.API_KEY)
    
    def upload_document(self, uploaded_file, session_id: str) -> Dict[str, Any]:
        """Upload and process a document"""
        # Save uploaded file temporarily
        temp_path = f"./temp_{session_id}_{uploaded_file.name}"
        
        try:
            # Save file
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            if self.mode == "LOCAL":
                # Use local function
                chunks = process_file(temp_path, session_id)
                return {
                    "status": "success",
                    "message": f"Processed {uploaded_file.name}",
                    "chunks_created": chunks
                }
            else:
                # Use API
                return self.api_client.upload_file(temp_path, session_id)
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Upload failed: {str(e)}"
            }
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def get_chat_response(self, user_message: str, history: List[Dict], session_id: str) -> Dict[str, Any]:
        """Get AI response to user message"""
        try:
            if self.mode == "LOCAL":
                # Use local function
                response = get_proview_response(
                    user_input=user_message,
                    chat_history=history,
                    session_id=session_id
                )
                
                # Convert to dict format
                return {
                    "ai_response": {
                        "interviewer_chat": response.interviewer_chat,
                        "is_correct": response.is_correct,
                        "score": response.score,
                        "refined_explanation": response.refined_explanation,
                        "suggested_replies": response.suggested_replies
                    }
                }
            else:
                # Use API
                return self.api_client.chat(user_message, history, session_id)
        
        except Exception as e:
            st.error(f"Error getting response: {str(e)}")
            return {
                "ai_response": {
                    "interviewer_chat": f"I encountered an error: {str(e)}",
                    "suggested_replies": ["Try again", "Reset session"]
                }
            }
    
    def clear_session(self, session_id: str) -> Dict[str, Any]:
        """Clear session data"""
        try:
            if self.mode == "LOCAL":
                deleted = clear_session_data(session_id)
                return {
                    "status": "success",
                    "message": "Session cleared",
                    "documents_deleted": deleted
                }
            else:
                return self.api_client.clear_session(session_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get session statistics"""
        try:
            if self.mode == "LOCAL":
                return get_session_stats(session_id)
            else:
                return self.api_client.get_session_stats(session_id)
        except Exception as e:
            return {"has_data": False, "document_count": 0}

# ============================================================================
# STREAMLIT UI HELPER FUNCTIONS
# ============================================================================

def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    if 'service' not in st.session_state:
        st.session_state.service = ProViewService()

def display_message(message: Dict[str, Any], is_user: bool = False):
    """Display a chat message"""
    if is_user:
        with st.chat_message("user", avatar="👤"):
            st.write(message["content"])
    else:
        with st.chat_message("assistant", avatar="🎯"):
            # Main response
            content = message["content"]
            if isinstance(content, dict):
                st.write(content.get("interviewer_chat", ""))
                
                # Show evaluation if available
                if content.get("is_correct") is not None:
                    if content["is_correct"]:
                        st.success(f"✅ Correct! Score: {content.get('score', 'N/A')}")
                    else:
                        st.warning(f"❌ Score: {content.get('score', 'N/A')}")
                
                # Show detailed feedback
                if content.get("refined_explanation"):
                    with st.expander("📝 Detailed Feedback"):
                        st.write(content["refined_explanation"])
                
                # Show suggested replies
                if content.get("suggested_replies"):
                    st.caption("💡 Suggested topics:")
                    for suggestion in content["suggested_replies"][:3]:
                        st.caption(f"• {suggestion}")
            else:
                st.write(content)

def format_history_for_api(messages: List[Dict]) -> List[Dict]:
    """Format message history for API"""
    formatted = []
    for msg in messages:
        formatted.append({
            "role": msg["role"],
            "content": msg["content"] if isinstance(msg["content"], str) else msg["content"]
        })
    return formatted

# ============================================================================
# MAIN STREAMLIT APP
# ============================================================================

def main():
    """Main Streamlit application"""
    
    # Page configuration
    st.set_page_config(
        page_title=AppConfig.APP_TITLE,
        page_icon=AppConfig.APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Get service instance
    service = st.session_state.service
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    
    with st.sidebar:
        st.title(f"{AppConfig.APP_ICON} ProView AI")
        st.caption("Your Interview Prep Coach")
        
        # Show mode
        mode_emoji = "💻" if service.mode == "LOCAL" else "☁️"
        st.info(f"{mode_emoji} Running in **{service.mode} MODE**")
        
        st.divider()
        
        # File Upload Section
        st.subheader("📄 Upload Documents")
        st.caption("Upload your resume or job description")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "docx", "txt"],
            help=f"Max size: {AppConfig.MAX_FILE_SIZE_MB}MB"
        )
        
        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            
            if file_size_mb > AppConfig.MAX_FILE_SIZE_MB:
                st.error(f"File too large! Max size: {AppConfig.MAX_FILE_SIZE_MB}MB")
            else:
                if st.button("📤 Upload & Process", use_container_width=True):
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        result = service.upload_document(uploaded_file, st.session_state.session_id)
                        
                        if result.get("status") == "success":
                            st.success(f"✅ {result.get('message')}")
                            if result.get("chunks_created"):
                                st.caption(f"Created {result['chunks_created']} document chunks")
                            st.session_state.uploaded_files.append(uploaded_file.name)
                        else:
                            st.error(f"❌ {result.get('message')}")
        
        # Show uploaded files
        if st.session_state.uploaded_files:
            st.divider()
            st.subheader("📎 Uploaded Files")
            for filename in st.session_state.uploaded_files:
                st.caption(f"✓ {filename}")
        
        st.divider()
        
        # Session Management
        st.subheader("⚙️ Session Controls")
        
        # Session stats
        if st.button("📊 Session Stats", use_container_width=True):
            stats = service.get_session_stats(st.session_state.session_id)
            if stats.get("has_data"):
                st.metric("Documents", stats.get("document_count", 0))
                if stats.get("file_count"):
                    st.metric("Files", stats["file_count"])
            else:
                st.info("No documents uploaded yet")
        
        # Clear session
        if st.button("🗑️ Clear Session", use_container_width=True, type="secondary"):
            if st.session_state.messages or st.session_state.uploaded_files:
                result = service.clear_session(st.session_state.session_id)
                st.session_state.messages = []
                st.session_state.uploaded_files = []
                st.session_state.session_id = str(uuid.uuid4())
                st.success("Session cleared!")
                st.rerun()
            else:
                st.info("Session already empty")
        
        # Reset chat only
        if st.button("🔄 Reset Chat", use_container_width=True):
            st.session_state.messages = []
            st.success("Chat history cleared!")
            st.rerun()
        
        st.divider()
        
        # Debug info
        if AppConfig.SHOW_DEBUG:
            st.subheader("🔧 Debug Info")
            st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
            st.caption(f"Messages: {len(st.session_state.messages)}")
            st.caption(f"Mode: {service.mode}")
            if service.mode == "API":
                st.caption(f"API: {AppConfig.API_BASE_URL}")
    
    # ========================================================================
    # MAIN CONTENT AREA
    # ========================================================================
    
    # Header
    st.title(f"{AppConfig.APP_ICON} ProView AI Interview Coach")
    st.markdown("""
    Get personalized interview preparation with AI-powered coaching.
    Upload your resume and job description to get started!
    """)
    
    # Quick start guide
    if not st.session_state.messages and not st.session_state.uploaded_files:
        st.info("""
        **👋 Welcome! Here's how to get started:**
        
        1. **Upload Documents** (sidebar): Upload your resume and/or job description
        2. **Start Chatting**: Tell me about the role you're interviewing for
        3. **Practice**: Answer interview questions and get feedback
        4. **Improve**: Review detailed feedback and suggestions
        """)
        
        # Sample starter prompts
        st.subheader("💡 Try these prompts:")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎯 Software Engineer Interview Prep", use_container_width=True):
                st.session_state.starter_prompt = "I'm preparing for a Software Engineer interview. Can you help me practice?"
                st.rerun()
            
            if st.button("📊 Product Manager Practice", use_container_width=True):
                st.session_state.starter_prompt = "I have a Product Manager interview coming up. Let's practice!"
                st.rerun()
        
        with col2:
            if st.button("💼 Behavioral Questions", use_container_width=True):
                st.session_state.starter_prompt = "I need help with behavioral interview questions."
                st.rerun()
            
            if st.button("🧮 Technical Coding Prep", use_container_width=True):
                st.session_state.starter_prompt = "Let's practice technical coding interview questions."
                st.rerun()
    
    st.divider()
    
    # ========================================================================
    # CHAT INTERFACE
    # ========================================================================
    
    # Display chat history
    for message in st.session_state.messages:
        display_message(message, is_user=(message["role"] == "user"))
    
    # Handle starter prompt
    if hasattr(st.session_state, 'starter_prompt'):
        user_input = st.session_state.starter_prompt
        delattr(st.session_state, 'starter_prompt')
    else:
        # Chat input
        user_input = st.chat_input("Type your message here...")
    
    # Process user input
    if user_input:
        # Add user message
        user_message = {
            "role": "user",
            "content": user_input
        }
        st.session_state.messages.append(user_message)
        
        # Display user message
        display_message(user_message, is_user=True)
        
        # Get AI response
        with st.chat_message("assistant", avatar="🎯"):
            with st.spinner("Thinking..."):
                # Format history
                history = format_history_for_api(st.session_state.messages[:-1])
                
                # Get response
                response_data = service.get_chat_response(
                    user_message=user_input,
                    history=history,
                    session_id=st.session_state.session_id
                )
                
                ai_response = response_data.get("ai_response", {})
                
                # Add to messages
                assistant_message = {
                    "role": "assistant",
                    "content": ai_response
                }
                st.session_state.messages.append(assistant_message)
                
                # Display response
                st.write(ai_response.get("interviewer_chat", ""))
                
                # Show evaluation
                if ai_response.get("is_correct") is not None:
                    if ai_response["is_correct"]:
                        st.success(f"✅ Correct! Score: {ai_response.get('score', 'N/A')}")
                    else:
                        st.warning(f"❌ Score: {ai_response.get('score', 'N/A')}")
                
                # Show feedback
                if ai_response.get("refined_explanation"):
                    with st.expander("📝 Detailed Feedback", expanded=True):
                        st.write(ai_response["refined_explanation"])
                
                # Show suggestions
                if ai_response.get("suggested_replies"):
                    st.caption("💡 Suggested topics:")
                    cols = st.columns(min(len(ai_response["suggested_replies"]), 3))
                    for idx, suggestion in enumerate(ai_response["suggested_replies"][:3]):
                        with cols[idx]:
                            if st.button(suggestion, key=f"suggestion_{idx}", use_container_width=True):
                                st.session_state.starter_prompt = suggestion
                                st.rerun()
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("💡 **Tip**: Upload your resume for personalized questions")
    with col2:
        st.caption(f"🔒 Session: `{st.session_state.session_id[:8]}...`")
    with col3:
        st.caption(f"⚡ Mode: {service.mode}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()