import streamlit as st
import uuid
import time
import os
import shutil
import logging
from typing import Optional

# For local development, load .env
from dotenv import load_dotenv
load_dotenv()

# --- CONFIG / API KEYS ---
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
PROVIEW_API_KEY = st.secrets.get("PROVIEW_API_KEY") or os.getenv("PROVIEW_API_KEY")
LANGCHAIN_API_KEY = st.secrets.get("LANGCHAIN_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = st.secrets.get("LANGCHAIN_TRACING_V2") or os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_PROJECT = st.secrets.get("LANGCHAIN_PROJECT") or os.getenv("LANGCHAIN_PROJECT")

# Validate keys
missing_keys = []
for key_name, key_value in [
    ("GROQ_API_KEY", GROQ_API_KEY),
    ("PROVIEW_API_KEY", PROVIEW_API_KEY),
    ("LANGCHAIN_API_KEY", LANGCHAIN_API_KEY)
]:
    if not key_value:
        missing_keys.append(key_name)

if missing_keys:
    st.error(f"⚠️ Initialization Failed: Missing API keys: {', '.join(missing_keys)}")
    st.stop()

# --- Import AI modules AFTER loading keys ---
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

# --- Page config ---
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

SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 min inactivity
if time.time() - st.session_state.last_activity > SESSION_TIMEOUT_SECONDS:
    try:
        clear_session_data(st.session_state.session_id)
        logger.info(f"🕐 Session {st.session_state.session_id[:8]} timed out and cleaned")
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
        logger.info("✅ ProView AI initialized successfully")
        return True, "System initialized successfully"
    except Exception as e:
        st.session_state.initialized = False
        error_msg = str(e)
        logger.error(f"❌ Initialization failed: {error_msg}")
        return False, error_msg

def process_uploaded_file(uploaded_file, session_id: str) -> tuple[bool, str]:
    try:
        file_ext = os.path.splitext(uploaded_file.name)[-1].lower()
        if file_ext not in ProViewConfig.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type. Allowed: {ProViewConfig.ALLOWED_EXTENSIONS}"
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
            return False, f"File too large. Max size: {ProViewConfig.MAX_FILE_SIZE_MB}MB"
        os.makedirs("./temp", exist_ok=True)
        temp_path = f"./temp/{session_id}_{uploaded_file.name}"
        try:
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            chunks_created = process_file(temp_path, session_id)
            logger.info(f"✅ Processed {uploaded_file.name} ({chunks_created} chunks)")
            return True, f"Successfully processed {uploaded_file.name} ({chunks_created} chunks)"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        logger.error(f"❌ Error processing file: {str(e)}")
        return False, f"Error: {str(e)}"

def reset_session():
    try:
        clear_session_data(st.session_state.session_id)
        logger.info(f"🧹 Session {st.session_state.session_id[:8]} cleared")
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.documents_uploaded = 0
    st.session_state.last_error = None

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
        logger.error(f"❌ Error getting AI response: {str(e)}")
        st.session_state.last_error = str(e)
        return {
            "interviewer_chat": f"I encountered an error: {str(e)}. Please try again or reset the session.",
            "suggested_replies": ["Reset session", "Try different question"]
        }

# --- INITIALIZE SYSTEM ---
if not st.session_state.initialized:
    with st.spinner("Initializing ProView AI..."):
        success, message = initialize_system()
        if not success:
            st.error(f"⚠️ Initialization Failed: {message}")
            st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ ProView Control")
    st.caption("Precision Interview Evaluation")
    with st.expander("🏥 System Status", expanded=False):
        if st.session_state.initialized:
            st.success("✅ System Online")
            st.code(f"Model: {ProViewConfig.MODEL_NAME}")
            st.code(f"Embedding: {ProViewConfig.EMBEDDING_MODEL}")
        else:
            st.error("❌ System Offline")

    st.divider()
    with st.expander("📊 Session Details", expanded=True):
        st.code(f"ID: {st.session_state.session_id[:12]}...")
        try:
            stats = get_session_stats(st.session_state.session_id)
            chunk_count = stats.get("document_count", 0)
        except:
            chunk_count = 0
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("💬 Messages", len(st.session_state.messages))
        with col_m2:
            st.metric("📄 Documents", st.session_state.documents_uploaded)
        st.metric("🧩 Indexed Chunks", chunk_count)
        if chunk_count > 0 or len(st.session_state.messages) > 0:
            st.success("✅ Session has active data")
        else:
            st.info("ℹ️ Session is empty")

    st.divider()
    with st.subheader("🗑️ Clear My Data"):
        col_clear1, col_clear2 = st.columns(2)
        with col_clear1:
            if st.button("Clear Chat Only", use_container_width=True):
                st.session_state.messages = []
                st.toast("💬 Chat history cleared!", icon="✅")
                st.rerun()
        with col_clear2:
            if st.button("Clear All Data", use_container_width=True):
                try:
                    stats = get_session_stats(st.session_state.session_id)
                    has_docs = stats.get("document_count", 0) > 0
                    has_chat = len(st.session_state.messages) > 0
                    if has_docs or has_chat:
                        deleted = clear_session_data(st.session_state.session_id)
                        st.session_state.messages = []
                        st.session_state.documents_uploaded = 0
                        st.toast(f"🗑️ Cleared! ({deleted} chunks + chat history)", icon="✅")
                        st.rerun()
                    else:
                        st.warning("ℹ️ No data to clear")
                except Exception as e:
                    st.error(f"Error clearing data: {str(e)}")

# --- MAIN APP HEADER ---
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.title("🎓 ProView AI Coach")
    st.markdown("Prepare for your next career move with **RAG-powered** interview simulation.")
with col2:
    st.success("🟢 Ready" if st.session_state.initialized else "🔴 Offline")

# --- FILE UPLOAD ---
with st.expander("📁 Knowledge Base (Upload Resume/Job Description)"):
    uploaded_files = st.file_uploader("Upload PDF/DOCX/TXT", accept_multiple_files=True, type=['pdf','docx','txt'])
    if uploaded_files:
        col_a, col_b = st.columns([0.7, 0.3])
        with col_a:
            st.info(f"{len(uploaded_files)} file(s) ready to upload")
        with col_b:
            if st.button("📤 Process Documents"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                success_count = 0
                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Processing {file.name}...")
                    success, message = process_uploaded_file(file, st.session_state.session_id)
                    if success: success_count += 1
                    else: st.warning(f"⚠️ {file.name}: {message}")
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                progress_bar.empty()
                status_text.empty()
                if success_count > 0:
                    st.session_state.documents_uploaded += success_count
                    st.toast(f"✅ Successfully indexed {success_count} file(s)!", icon="✅")
                    st.rerun()
                else:
                    st.error("❌ Failed to process files.")

# --- CHAT DISPLAY ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if isinstance(content, dict):
            st.markdown(content.get("interviewer_chat", ""))
            if content.get("is_correct") is not None:
                st.markdown("---")
                col_score, col_feedback = st.columns([0.2, 0.8])
                with col_score:
                    score = content.get("score", "N/A")
                    st.success(f"✅ {score}" if content.get("is_correct") else f"❌ {score}")
                with col_feedback:
                    explanation = content.get("refined_explanation", "")
                    if explanation: st.info(f"**Feedback:** {explanation}")
            if content.get("suggested_replies"):
                st.caption("💡 Suggested responses:")
                for reply in content.get("suggested_replies", []):
                    st.caption(f"• {reply}")
        else:
            st.markdown(content)

# --- CHAT INPUT ---
if prompt := st.chat_input("Start by telling ProView which role you're interviewing for..."):
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("<p class='processing'>🤔 ProView is thinking...</p>", unsafe_allow_html=True)
        ai_data = get_ai_response(prompt, st.session_state.messages, st.session_state.session_id)
        placeholder.empty()
        st.markdown(ai_data.get("interviewer_chat",""))
        if ai_data.get("is_correct") is not None:
            st.markdown("---")
            col_score, col_feedback = st.columns([0.2,0.8])
            with col_score:
                score = ai_data.get("score","N/A")
                st.success(f"✅ {score}" if ai_data.get("is_correct") else f"❌ {score}")
            with col_feedback:
                explanation = ai_data.get("refined_explanation","")
                if explanation: st.info(f"**Feedback:** {explanation}")
        if ai_data.get("suggested_replies"):
            st.caption("💡 Suggested responses:")
            for reply in ai_data.get("suggested_replies", []):
                st.caption(f"• {reply}")
        st.session_state.messages.append({"role":"assistant","content":ai_data})

# --- FOOTER ---
st.markdown("---")
col_f1, col_f2 = st.columns([0.7,0.3])
with col_f1: st.caption("🔒 Privacy-First: Your data is session-isolated and auto-deleted after 30 min of inactivity.")
with col_f2: st.caption(f"⏱️ Session: {int((time.time() - st.session_state.session_created)/60)}min")
st.caption("💡 Deployed on Streamlit Cloud: vector DB is temporary and never committed to GitHub.")
