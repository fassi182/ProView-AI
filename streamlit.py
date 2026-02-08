import streamlit as st
import uuid
import time
import os
import logging
from typing import Optional

# Load local .env if exists
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
        st.error(f"❌ Backend error: {str(e)}")  # Show real error
        return {
            "interviewer_chat": "I encountered an error. Please try again or reset the session.",
            "suggested_replies": ["Reset session", "Try different question"]
        }

def reset_session():
    try:
        clear_session_data(st.session_state.session_id)
    except:
        pass
    st.session_state.messages = []
    st.session_state.documents_uploaded = 0
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.last_error = None

# --- INITIALIZE SYSTEM ---
if not st.session_state.initialized:
    with st.spinner("Initializing ProView AI..."):
        success, message = initialize_system()
        if not success:
            st.error(f"⚠️ Initialization Failed: {message}")
            st.stop()

# --- PAGE GUI ---
# Inject CSS for styling
st.markdown("""
<style>
.main { background-color: #0e1117; }
.stChatMessage { border-radius: 15px; margin-bottom: 10px; }
.status-box { padding: 10px; border-radius: 10px; border: 1px solid #30363d; background-color: #161b22; margin-bottom: 20px; }
.processing { animation: pulse 1.5s infinite; color: #58a6ff; font-weight: bold; }
.metric-container { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin: 10px 0; }
@keyframes pulse {0% { opacity: 1; }50% { opacity: 0.5; }100% { opacity: 1; }}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ ProView Control")
    st.caption("Precision Interview Evaluation")

    # Session info
    st.subheader("📊 Session Info")
    st.code(f"ID: {st.session_state.session_id[:12]}...")
    st.metric("💬 Messages", len(st.session_state.messages))
    st.metric("📄 Documents", st.session_state.documents_uploaded)

    # Clear session buttons
    if st.button("Clear Chat Only"):
        st.session_state.messages = []
        st.toast("💬 Chat cleared", icon="✅")
        st.rerun()
    if st.button("Clear All Data"):
        reset_session()
        st.toast("🗑️ All session data cleared", icon="✅")
        st.rerun()

# Header
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.title("🎓 ProView AI Coach")
    st.markdown("Prepare for your next career move with **RAG-powered** interview simulation.")
with col2:
    st.success("🟢 Ready")

# File upload
with st.expander("📁 Knowledge Base (Upload Resume/Job Description)"):
    uploaded_files = st.file_uploader(
        "Upload PDF/DOCX/TXT", accept_multiple_files=True,
        type=['pdf', 'docx', 'txt'], label_visibility="collapsed"
    )
    if uploaded_files:
        for file in uploaded_files:
            success, msg = process_uploaded_file(file, st.session_state.session_id)
            st.toast(msg if success else f"⚠️ {msg}")

# Display chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"] if isinstance(msg["content"], str) else msg["content"].get("interviewer_chat", ""))

# Chat input
if prompt := st.chat_input("Start by telling ProView which role you're interviewing for..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("<p class='processing'>🤔 ProView is thinking...</p>", unsafe_allow_html=True)
        ai_data = get_ai_response(prompt, st.session_state.messages, st.session_state.session_id)
        placeholder.empty()
        st.markdown(ai_data.get("interviewer_chat", ""))
        st.session_state.messages.append({"role": "assistant", "content": ai_data})

# Footer
st.markdown("---")
st.caption("🔒 Privacy-First: Data is session-isolated and auto-deleted after 30 minutes.")
