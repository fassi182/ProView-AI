#streamlit.py
import streamlit as st
import time
from app.services import get_proview_response
from app.schemas import ProViewCoachOutput
from app.config import ProViewConfig

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="ProView AI Coach",
    page_icon="🎯",
    layout="wide"
)

# ---------------- SIMPLE CSS ----------------
st.markdown("""
<style>
.stChatMessage {
    padding: 12px;
    border-radius: 10px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🎯 ProView AI Coach")

    try:
        ProViewConfig.validate()
        st.success("API Connected ✅")
    except:
        st.error("Missing API Key ❌")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ---------------- TITLE ----------------
st.title("🎯ProView")
st.caption("Practice interviews with AI, get instant feedback, and level up your skills.")

# ---------------- SHOW CHAT HISTORY ----------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------- STREAMING FUNCTION ----------------
def stream_text(text: str):
    placeholder = st.empty()
    output = ""

    for char in text:
        output += char
        placeholder.markdown(output)
        time.sleep(0.01)

# ---------------- USER INPUT ----------------
prompt = st.chat_input("Type your answer...")

if prompt:

    # 1. Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. AI RESPONSE
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):

            chat_history = st.session_state.messages[:-1]
            response: ProViewCoachOutput = get_proview_response(prompt, chat_history)

            # ---------------- BUILD ONE FINAL MESSAGE ----------------
            final_message = response.interviewer_chat

            if response.score:
                final_message += f"\n\n📊 Score: {response.score}"

            if response.refined_explanation:
                final_message += f"\n\n🧠 Feedback:\n{response.refined_explanation}"

            if response.suggested_replies:
                final_message += "\n\n💡 Suggestions:"
                for s in response.suggested_replies:
                    final_message += f"\n👉 {s}"

            # ---------------- STREAM OUTPUT ----------------
            stream_text(final_message)

    # 3. SAVE MESSAGE
    st.session_state.messages.append({
        "role": "assistant",
        "content": final_message
    })