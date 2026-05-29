import streamlit as st
import time
import requests

# CONFIG
API_BASE_URL = "https://fassiurrehman-proview-api.hf.space" # Your API URL
st.set_page_config(page_title="ProView AI Coach", page_icon="🎯", layout="wide")

# SESSION STATE
if "messages" not in st.session_state:
    st.session_state.messages = []

# SIDEBAR: RAG UPLOAD
with st.sidebar:
    st.title("🎯 ProView AI Coach")
    uploaded_file = st.file_uploader("Upload Interview Context (PDF/TXT)", type=["pdf", "txt"])
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# CHAT INTERFACE
st.title("🎯 ProView")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# STREAMING
def stream_text(text: str):
    placeholder = st.empty()
    output = ""
    for char in text:
        output += char
        placeholder.markdown(output)
        time.sleep(0.01)

# USER INPUT
prompt = st.chat_input("Type your answer...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                # Prepare payload
                payload = {
                    "query": prompt,
                    "chat_history": st.session_state.messages[:-1]
                }
                
                # If file uploaded, you'd handle that via a multipart request
                # Here we assume a standard JSON API call
                response = requests.post(f"{API_BASE_URL}/api/v1/chat/ask", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    # Formatting response from your API schema
                    final_message = f"{data.get('interviewer_chat', '')}\n\n"
                    if data.get('score'): final_message += f"📊 Score: {data['score']}\n\n"
                    if data.get('refined_explanation'): final_message += f"🧠 Feedback:\n{data['refined_explanation']}"
                    
                    stream_text(final_message)
                    st.session_state.messages.append({"role": "assistant", "content": final_message})
                else:
                    st.error("API Error: Unable to get response.")
            except Exception as e:
                st.error(f"Connection Error: {e}")