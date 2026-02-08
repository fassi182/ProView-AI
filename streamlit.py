# streamlit_app.py
import streamlit as st
import uuid
import time
import os
import logging
from typing import Optional

# Import AI logic modules
from app.services import get_proview_response
from app.rag_storage import (
    process_file,
    get_session_stats,
    clear_session_data,
    janitor_cleanup
)
from app.config import ProViewConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="ProView AI | Interview Coach",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ENVIRONMENT SETUP ---
@st.cache_resource
def setup_environment():
    """Initialize environment and validate configuration"""
    try:
        # Setup environment variables from secrets/env
        ProViewConfig.setup_environment()
        ProViewConfig.validate()
        
        # Run background cleanup
        try:
            janitor_cleanup()
        except Exception as e:
            logger.warning(f"Background cleanup failed: {str(e)}")
        
        logger.info("✅ ProView AI initialized successfully")
        return True, "System initialized successfully"
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Initialization failed: {error_msg}")
        return False, error_msg

# --- CUSTOM STYLING ---
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .status-box {
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #30363d;
        background-color: #161b22;
        margin-bottom: 20px;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .processing { animation: pulse 1.5s infinite; color: #58a6ff; font-weight: bold; }
    .metric-container {
        background: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
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

# Update last activity time
st.session_state.last_activity = time.time()

# Check for session timeout
SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 minutes
if time.time() - st.session_state.last_activity > SESSION_TIMEOUT_SECONDS:
    try:
        clear_session_data(st.session_state.session_id)
        logger.info(f"🕐 Session {st.session_state.session_id[:8]}... timed out")
    except:
        pass
    st.session_state.messages = []
    st.session_state.documents_uploaded = 0
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.session_created = time.time()

# --- HELPER FUNCTIONS ---
def process_uploaded_file(uploaded_file, session_id: str) -> tuple[bool, str]:
    """Process uploaded file and add to vector database"""
    try:
        # Validate file extension
        file_ext = os.path.splitext(uploaded_file.name)[-1].lower()
        if file_ext not in ProViewConfig.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type. Allowed: {ProViewConfig.ALLOWED_EXTENSIONS}"
        
        # Validate file size
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > ProViewConfig.MAX_FILE_SIZE_MB:
            return False, f"File too large. Max size: {ProViewConfig.MAX_FILE_SIZE_MB}MB"
        
        # Create temp directory
        os.makedirs("./temp", exist_ok=True)
        
        # Save temporarily
        temp_path = f"./temp/{session_id}_{uploaded_file.name}"
        try:
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Process file
            chunks_created = process_file(temp_path, session_id)
            
            logger.info(f"✅ Processed {uploaded_file.name} ({chunks_created} chunks)")
            return True, f"Successfully processed {uploaded_file.name} ({chunks_created} chunks)"
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"❌ Error processing file: {str(e)}")
        return False, f"Error: {str(e)}"

def get_ai_response(user_message: str, history: list, session_id: str) -> dict:
    """Get AI response from services module"""
    try:
        # Convert Streamlit message format
        formatted_history = []
        for msg in history[-10:]:  # Keep last 10 messages
            formatted_history.append({
                "role": msg["role"],
                "content": msg["content"] if isinstance(msg["content"], str) else msg["content"]
            })
        
        # Get response
        response = get_proview_response(
            user_input=user_message,
            chat_history=formatted_history,
            session_id=session_id
        )
        
        # Convert Pydantic model to dict
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
            "interviewer_chat": f"I apologize, but I encountered an error: {str(e)}. Please try again or reset the session.",
            "suggested_replies": ["Reset session", "Try different question"]
        }

# --- INITIALIZATION CHECK ---
if not st.session_state.initialized:
    with st.spinner("Initializing ProView AI..."):
        success, message = setup_environment()
        if not success:
            st.error(f"⚠️ **Initialization Failed**: {message}")
            st.info("💡 **Setup Instructions:**")
            st.markdown("""
            **For Local Development:**
            1. Create a `.env` file in the project root
            2. Add: `GROQ_API_KEY=your_key_here`
            
            **For Streamlit Cloud:**
            1. Go to your app settings
            2. Navigate to "Secrets"
            3. Add:
```toml
            GROQ_API_KEY = "your_key_here"
```
            """)
            st.stop()
        st.session_state.initialized = True

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ ProView Control")
    st.caption("Precision Interview Evaluation")
    
    # System Status
    with st.expander("🏥 System Status", expanded=False):
        if st.session_state.initialized:
            st.success("✅ System Online")
            st.code(f"Model: {ProViewConfig.MODEL_NAME}", language="text")
            st.code(f"Embedding: {ProViewConfig.EMBEDDING_MODEL}", language="text")
            
            # Show environment source
            try:
                import streamlit as st_check
                if hasattr(st_check, 'secrets') and 'GROQ_API_KEY' in st_check.secrets:
                    st.info("📡 Using Streamlit Cloud Secrets")
                else:
                    st.info("📁 Using Local .env File")
            except:
                st.info("📁 Using Local .env File")
        else:
            st.error("❌ System Offline")
    
    st.divider()
    
    # Session Details
    with st.expander("📊 Session Details", expanded=True):
        st.code(f"ID: {st.session_state.session_id[:12]}...", language="text")
        
        # Get session stats
        try:
            stats = get_session_stats(st.session_state.session_id)
            chunk_count = stats.get("document_count", 0)
        except:
            chunk_count = 0
        
        # Visual metrics
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("💬 Messages", len(st.session_state.messages))
        with col_m2:
            st.metric("📄 Documents", st.session_state.documents_uploaded)
        
        st.metric("🧩 Indexed Chunks", chunk_count)
        
        # Status summary
        if chunk_count > 0 or len(st.session_state.messages) > 0:
            st.success("✅ Session has active data")
        else:
            st.info("ℹ️ Session is empty")
    
    st.divider()
    
    # Clear Data Section
    st.subheader("🗑️ Clear My Data")
    
    with st.expander("ℹ️ What's the difference?", expanded=False):
        st.markdown("""
        **Clear Chat Only:** 
        - ✅ Removes conversation history
        - ❌ Keeps uploaded documents
        - Use: Start fresh conversation with same context
        
        **Clear All Data:**
        - ✅ Removes conversation history
        - ✅ Removes uploaded documents from database
        - Use: Complete reset of your session
        """)
    
    col_clear1, col_clear2 = st.columns(2)
    
    with col_clear1:
        if st.button("Clear Chat Only", use_container_width=True, type="secondary"):
            st.session_state.messages = []
            st.toast("💬 Chat history cleared!", icon="✅")
            time.sleep(0.5)
            st.rerun()
    
    with col_clear2:
        if st.button("Clear All Data", use_container_width=True, type="primary"):
            try:
                stats = get_session_stats(st.session_state.session_id)
                has_docs = stats.get("document_count", 0) > 0
                has_chat = len(st.session_state.messages) > 0
                
                if not has_docs and not has_chat:
                    st.warning("ℹ️ No data to clear - session is already empty!")
                else:
                    with st.spinner("Clearing your session data..."):
                        deleted = clear_session_data(st.session_state.session_id)
                        st.session_state.messages = []
                        st.session_state.documents_uploaded = 0
                        st.toast(f"🗑️ Cleared! ({deleted} chunks + chat history)", icon="✅")
                        time.sleep(1)
                        st.rerun()
            except Exception as e:
                st.error(f"Error clearing data: {str(e)}")
    
    st.divider()
    
    # Privacy Notice
    with st.expander("🔒 Privacy & Data", expanded=False):
        st.caption("🔐 **Your data is private and temporary:**")
        st.caption("✅ Each session is isolated")
        st.caption("✅ Data auto-deletes after 2 hours of inactivity")
        st.caption("✅ Use 'Clear All Data' to delete immediately")
        st.caption(f"📍 Session ID: `{st.session_state.session_id[:16]}...`")
    
    # Error Display
    if st.session_state.last_error:
        st.divider()
        with st.container():
            st.error(f"⚠️ Last Error: {st.session_state.last_error}")
            if st.button("Clear Error", use_container_width=True):
                st.session_state.last_error = None
                st.rerun()

# --- MAIN HEADER ---
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.title("🎓 ProView AI Coach")
    st.markdown("Prepare for your next career move with **RAG-powered** interview simulation.")
    
with col2:
    if st.session_state.initialized:
        st.success("🟢 Ready")
    else:
        st.error("🔴 Offline")

# --- KNOWLEDGE BASE UPLOADER ---
with st.expander("📁 Knowledge Base (Upload Resume or Job Description)", expanded=False):
    st.caption("Upload your resume, job description, or any relevant documents to personalize your interview experience.")
    
    uploaded_files = st.file_uploader(
        "Upload PDF/DOCX/TXT files", 
        accept_multiple_files=True,
        type=['pdf', 'docx', 'txt'],
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        col_a, col_b = st.columns([0.7, 0.3])
        with col_a:
            st.info(f"📄 {len(uploaded_files)} file(s) ready to upload")
        with col_b:
            if st.button("📤 Process Documents", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                success_count = 0
                
                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Processing {file.name}...")
                    
                    success, message = process_uploaded_file(file, st.session_state.session_id)
                    
                    if success:
                        success_count += 1
                    else:
                        st.warning(f"⚠️ {file.name}: {message}")
                    
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                progress_bar.empty()
                status_text.empty()
                
                if success_count > 0:
                    st.session_state.documents_uploaded += success_count
                    st.toast(f"✅ Successfully indexed {success_count} file(s)!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to process files. Check the error messages above.")

# --- CHAT DISPLAY ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], dict):
            content = msg["content"]
            
            # Main chat message
            st.markdown(content.get("interviewer_chat", ""))
            
            # Feedback section
            if content.get("is_correct") is not None:
                st.markdown("---")
                
                col_score, col_feedback = st.columns([0.2, 0.8])
                
                with col_score:
                    score = content.get("score", "N/A")
                    is_correct = content.get("is_correct", False)
                    
                    if is_correct:
                        st.success(f"✅ {score}")
                    else:
                        st.error(f"❌ {score}")
                
                with col_feedback:
                    explanation = content.get("refined_explanation", "")
                    if explanation:
                        st.info(f"**Feedback:** {explanation}")
            
            # Suggested replies
            if content.get("suggested_replies"):
                st.caption("💡 Suggested responses:")
                for reply in content.get("suggested_replies", []):
                    st.caption(f"• {reply}")
        else:
            st.markdown(msg["content"])

# --- CHAT INPUT & PROCESSING ---
if prompt := st.chat_input("Start by telling ProView which role you're interviewing for..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI Response
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("<p class='processing'>🤔 ProView is thinking...</p>", unsafe_allow_html=True)
        
        # Get AI response
        ai_data = get_ai_response(
            user_message=prompt,
            history=st.session_state.messages,
            session_id=st.session_state.session_id
        )
        
        placeholder.empty()
        
        # Render response
        st.markdown(ai_data.get("interviewer_chat", ""))
        
        # Render feedback
        if ai_data.get("is_correct") is not None:
            st.markdown("---")
            
            col_score, col_feedback = st.columns([0.2, 0.8])
            
            with col_score:
                score = ai_data.get("score", "N/A")
                is_correct = ai_data.get("is_correct", False)
                
                if is_correct:
                    st.success(f"✅ {score}")
                else:
                    st.error(f"❌ {score}")
            
            with col_feedback:
                explanation = ai_data.get("refined_explanation", "")
                if explanation:
                    st.info(f"**Feedback:** {explanation}")
        
        # Suggested replies
        if ai_data.get("suggested_replies"):
            st.caption("💡 Suggested responses:")
            for reply in ai_data.get("suggested_replies", []):
                st.caption(f"• {reply}")
        
        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": ai_data})

# --- FOOTER ---
st.markdown("---")
col_f1, col_f2 = st.columns([0.7, 0.3])
with col_f1:
    st.caption("🔒 **Privacy-First Design:** Your data is session-isolated and auto-deleted after 30 minutes of inactivity.")
with col_f2:
    st.caption(f"⏱️ Session: {int((time.time() - st.session_state.session_created) / 60)}min")