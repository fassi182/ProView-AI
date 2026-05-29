import streamlit as st
import requests

st.set_page_config(page_title="ProView AI", layout="wide")
st.title("🎯 ProView AI Coach")

# Your verified API URL
API_BASE_URL = "https://fassiurrehman-proview-api.hf.space"

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask for interview feedback..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing your response..."):
            try:
                # Direct call to your API
                response = requests.post(f"{API_BASE_URL}/api/v1/chat/ask", 
                                         json={"query": prompt, "chat_history": st.session_state.messages})
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("interviewer_chat", "Thank you for your response.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.warning("The ProView engine is currently warming up. Please try again in a moment.")
            except Exception:
                st.error("Connection temporarily unavailable. Our system is scaling to meet demand.")