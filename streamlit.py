import streamlit as st
import uuid
import time
import os
import logging
from typing import Optional

# Local .env support
from dotenv import load_dotenv
load_dotenv()

# --- SECRETS / API KEYS ---
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
PROVIEW_API_KEY = st.secrets.get("PROVIEW_API_KEY") or os.getenv("PROVIEW_API_KEY")
LANGCHAIN_API_KEY = st.secrets.get("LANGCHAIN_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = st.secrets.get("LANGCHAIN_TRACING_V2") or os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_PROJECT = st.secrets.get("LANGCHAIN_PROJECT") or os.getenv("LANGCHAIN_PROJECT")

# --- VALIDATE KEYS ---
missing_keys = [k for k, v in [
    ("GROQ_API_KEY", GROQ_API_KEY),
    ("PROVIEW_API_KEY", PROVIEW_API_KEY),
    ("LANGCHAIN_API_KEY", LANGCHAIN_API_KEY)
] if not v]

if missing_keys:
    st.error(f"⚠️ Missing API keys: {', '.join(missing_keys)}")
    st.stop()

# --- IMPORT YOUR MODULES AFTER LOADING KEYS ---
from app.services import get_proview_response
from app.rag_storage import (
    process_file,
    get_session_stats,
    clear_session_data,
    janitor_cleanup
)
from app.config import ProViewConfig

# Set keys in config
ProViewConfig.GROQ_API_KEY = GROQ_API_KEY
ProViewConfig.PROVIEW_API_KEY = PROVIEW_API_KEY
ProViewConfig.LANGCHAIN_API_KEY = LANGCHAIN_API_KEY
ProViewConfig.LANGCHAIN_TRACING_V2 = LANGCHAIN_TRACING_V2
ProViewConfig.LANGCHAIN_PROJECT = LANGCHAIN_PROJECT

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="ProView AI | Interview Coach",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.session_created = time.time()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "documents_uploaded" not in st.session_state:
    st.session_state.documents_uploaded = 0
if "last_error" not in st.session_state:
    st.session_state.last_error = None
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()

st.session_state.last_activity = time.time()

SESSION_TIMEOUT_SECONDS = 30 * 60
if time.time() - st.session_state.last_activity > SESSION_TIMEOUT_SECONDS:
    try:
        clear_session_data(st.session_state.session_id)
    except:
        pass
    st.session_state.messages = []
    st.session_state.documents_uploaded = 0
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.session_created = time.time()

# --- HELPER FUNCTIONS ---
def initialize_system():
    try:
        ProViewConfig.validate()
        try:
            janitor_cleanup()
        except Exception as e:
            logger.warning(f"Background cleanup failed: {str(e)}")
        st.session_state.initialized = True
        return True, "System initialized successfully"
    except Exception as e:
        st.session_state.initialized = False
        return False, str(e)

def process_uploaded_file(uploaded_file, session_id: str):
    try:
        file_ext = os.path.splitext(uploaded_file.name)[-1].lower()
        if file_ext not in ProViewConfig.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type. Allowed: {ProViewConfig.ALLOWED_EXTENSIONS}"
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
            return False, f"File too large. Max size: {ProViewConfig.MAX_FILE_SIZE_MB}MB"
        os.makedirs("./temp", exist_ok=True)
        temp_path = f"./temp/{session_id}_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        chunks_created = process_file(temp_path, session_id)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return True, f"Successfully processed {uploaded_file.name} ({chunks_created} chunks)"
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return False, str(e)

def get_ai_response(user_message: str, history: list, session_id: str) -> dict:
    try:
        formatted_history = [{"role": msg["role"], "content": msg["content"]} for msg in history[-10:]]
        response = get_proview_response(user_input=user_message, chat_history=formatted_history, session_id=session_id)
        return {
            "interviewer_chat": response.interviewer_chat,
            "is_correct": response.is_correct,
            "score": response.score,
            "refined_explanation": response.refined_explanation,
            "suggested_replies": response.suggested_replies
        }
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        st.error(f"❌ Backend error: {str(e)}")  # Shows real error
        return {
            "interviewer_chat": "I encountered an error. Please try again or reset the session.",
            "suggested_replies": ["Reset session", "Try different question"]
        }

# --- INITIALIZE SYSTEM ---
if not st.session_state.initialized:
    with st.spinner("Initializing ProView AI..."):
        success, message = initialize_system()
        if not success:
            st.error(f"Initialization failed: {message}")
            st.stop()

# --- SIDEBAR, CHAT INPUT, FILE UPLOAD, FOOTER ---
# You can include all your previous sidebar, chat input, and file upload code here
# (I can integrate full HTML+CSS + sidebar if needed)

st.title("🎓 ProView AI Coach")
st.write("Prepare for your next career move with RAG-powered interview simulation.")
