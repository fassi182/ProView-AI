# 🎯 ProView AI Coach

> AI-Powered Interview Preparation Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-UI-red) ![LangChain](https://img.shields.io/badge/LangChain-Orchestration-green) ![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-purple)

---
## 🚀 Live Demo
Check out the app here: https://proview-ai-85hp9t9gwe4ff4o6dp4x6b.streamlit.app/

---

## Overview

ProView AI Coach is an intelligent, conversational interview preparation tool built with **Streamlit** and powered by **Groq's LLaMA 3.3 70B** model via LangChain. It simulates realistic interview sessions, evaluates your answers, and provides structured feedback to help you land your dream job.

---

## Features

- 🎯 **Role-aware simulation** — adapts questions based on job role, seniority, and interview type
- 📊 **Real-time evaluation** — scores answers (X/10) with targeted improvement suggestions
- 📈 **Adaptive difficulty** — starts easy, increases based on your performance
- 📄 **Context-aware questioning** — personalizes questions using resume or job description
- ⚡ **Streaming responses** — character-by-character output for a natural conversation feel
- 💬 **Full chat history** — maintains context across the entire session

---

## Project Structure

```
proview-ai-coach/
│
├── streamlit.py          # Main app entry point — UI, chat history, streaming
├── app/
│   ├── config.py         # Config class — loads API key, model name, temperature
│   ├── llm_logic.py      # LangChain chain, system prompt, history formatter
│   ├── schemas.py        # Pydantic models — ProViewCoachOutput, MessageModel
│   └── services.py       # Service layer — invokes LLM chain, handles errors
│
├── .env                  # Environment variables (not committed to git)
├── requirements.txt      # Python dependencies
└── .gitignore            # Files excluded from version control
```

---

## Prerequisites

- Python 3.9+
- A **Groq API Key** — get one free at [console.groq.com](https://console.groq.com)
- `pip` package manager

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/proview-ai-coach.git
cd proview-ai-coach
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 5. Run the App

```bash
streamlit run streamlit.py
```

The app will open in your browser at `http://localhost:8501`

---

## requirements.txt

```
streamlit
langchain
langchain-groq
langchain-core
pydantic
python-dotenv
```

---

## .gitignore

```
.env
__pycache__/
*.pyc
.venv/
venv/
.DS_Store
```

---

## How It Works

### System Prompt

ProView AI Coach operates under a detailed system prompt that instructs the model to:

- Identify the target **job role and seniority level** before starting
- Ask **realistic, role-specific** interview questions
- **Score answers** on a 1–10 scale with targeted improvement suggestions
- **Adapt difficulty** progressively based on user performance
- Return responses in a **structured Pydantic schema**

### Response Schema

Every AI response is parsed into:

| Field | Description |
|---|---|
| `interviewer_chat` | Main response / next question (**always required**) |
| `score` | `"X/10"` rating (only after an answer is evaluated) |
| `refined_explanation` | Detailed feedback (optional) |
| `suggested_replies` | 2–3 improvement suggestions (optional list) |

### Streaming Output

Responses are displayed **character-by-character** using Streamlit's `st.empty()` placeholder, giving the feel of a live conversation.

---

## Usage Guide

### Starting a Session

1. Open the app and describe your goal, e.g.:
   > *"I want to practice for a Senior Backend Engineer role"*
2. The coach confirms the role, level, and interview type, then begins
3. Answer naturally as you would in a real interview
4. Receive **immediate scores, feedback, and follow-up questions**

### Sidebar Controls

| Control | Description |
|---|---|
| ✅ API Connected | Confirms your Groq API key is loaded |
| 🗑️ Clear Chat | Resets the session to start fresh |

---

## Architecture

```
streamlit.py       →  Presentation layer  (UI, rendering, streaming)
app/services.py    →  Application layer   (orchestrates LLM calls)
app/llm_logic.py   →  Domain layer        (LangChain chain, prompt, history)
app/schemas.py     →  Data layer          (Pydantic structured output models)
app/config.py      →  Infrastructure      (environment config, model settings)
```

---

## Model Information

| Setting | Value |
|---|---|
| Model | `llama-3.3-70b-versatile` |
| Provider | Groq |
| Temperature | `0.7` |
| Structured Output | LangChain `.with_structured_output()` + Pydantic |

---

*ProView AI Coach — Built with Streamlit, LangChain & Groq*