# 🎓 ProView AI - RAG-Powered Interview Coach

A production-ready interview preparation system built with FastAPI, LangChain, and RAG (Retrieval Augmented Generation) technology. Upload your resume and job descriptions to get personalized, context-aware interview coaching.

## 🎯 What is ProView AI?

ProView AI is an intelligent interview coach that:
- **Simulates realistic interviews** based on your target role and experience level
- **Evaluates your answers** with detailed feedback and scoring (0-10 scale)
- **Personalizes questions** using your resume and job description context via RAG
- **Maintains conversation history** across chat sessions

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │ (Streamlit UI or API Consumer)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│      FastAPI REST API               │
│  ┌──────────┐  ┌─────────────┐    │
│  │Endpoints │  │Rate Limiting│    │
│  └──────────┘  └─────────────┘    │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│       Services Layer                │
│  ┌──────────────┐  ┌────────────┐  │
│  │ LLM Pipeline │  │RAG Storage │  │
│  └──────────────┘  └────────────┘  │
└──────┬───────────────────┬──────────┘
       │                   │
       ▼                   ▼
┌─────────────┐    ┌──────────────┐
│   Groq      │    │   Chroma DB  │
│  (LLaMA 3.3)│    │  (Vector DB) │
└─────────────┘    └──────────────┘
```

## 🛠️ Tech Stack

**Backend Framework:**
- FastAPI - High-performance REST API framework
- Pydantic - Data validation and schema modeling

**LLM & AI:**
- LangChain - LLM orchestration and prompt management
- Groq - Ultra-fast LLM inference (LLaMA 3.3 70B)
- LangChain-Groq - Groq integration for LangChain

**Vector Database & Embeddings:**
- ChromaDB - Vector database for document storage
- HuggingFace Embeddings - Sentence transformers (all-MiniLM-L6-v2)
- LangChain-Chroma - ChromaDB integration

**Document Processing:**
- PyPDF - PDF document parsing
- Docx2txt - Word document parsing
- RecursiveCharacterTextSplitter - Document chunking

**UI (Optional):**
- Streamlit - Interactive web interface

**Utilities:**
- python-dotenv - Environment variable management
- uvicorn - ASGI server

## ✨ Implemented Features

### 🔒 **Security & Access Control**
- ✅ API key authentication via `X-ProView-Key` header
- ✅ Session-based data isolation (cryptographic session IDs)
- ✅ Rate limiting (10 requests/60 seconds per IP)
- ✅ File size validation (10MB max)
- ✅ File type validation (PDF/DOCX/TXT only)
- ✅ Pydantic schema validation on all inputs

### 🧠 **AI Interview Coaching**
- ✅ Role-aware question generation
- ✅ Answer evaluation with boolean correctness flag
- ✅ 0-10 scoring system with detailed feedback
- ✅ Structured output with `ProViewCoachOutput` schema
- ✅ Suggested reply recommendations (2-3 per response)
- ✅ Context-aware responses using RAG

### 📚 **RAG & Document Management**
- ✅ Multi-format document upload (PDF, DOCX, TXT)
- ✅ Automatic document chunking (700 char chunks, 100 char overlap)
- ✅ Vector embeddings with HuggingFace all-MiniLM-L6-v2
- ✅ Similarity search with k=3 retrieval
- ✅ Session-isolated document storage
- ✅ Metadata tagging (session_id, timestamp, source_file)

### 🗄️ **Session Management**
- ✅ UUID-based session identification
- ✅ Automatic session cleanup (2-hour timeout)
- ✅ Manual session data clearing
- ✅ Session statistics endpoint
- ✅ Background janitor cleanup tasks

### 🚀 **Performance & Optimization**
- ✅ Singleton pattern for LLM initialization
- ✅ Lazy loading of embeddings model
- ✅ Background task processing
- ✅ Efficient document retrieval with filters
- ✅ Comprehensive logging (INFO/WARNING/ERROR levels)

### 🖥️ **User Interface (Streamlit)**
- ✅ Interactive chat interface
- ✅ File upload widget with progress tracking
- ✅ Session statistics display
- ✅ Real-time feedback rendering
- ✅ Clear session functionality
- ✅ Auto-cleanup on inactivity (30 min timeout)

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Groq API key ([get one here](https://console.groq.com))

### Installation

1. **Clone and install**
```bash
git clone https://github.com/yourusername/proview-ai.git
cd proview-ai
pip install -r requirements.txt
```

2. **Configure environment**
```bash
# Create .env file
GROQ_API_KEY=your_groq_api_key_here
PROVIEW_API_KEY=your_secure_random_key_here
```

3. **Run the API**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

4. **Run Streamlit UI (optional)**
```bash
streamlit run streamlit_app.py
```

## 📡 API Endpoints

### Authentication
All endpoints require: `X-ProView-Key: your_api_key`

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/upload` | POST | Upload documents (PDF/DOCX/TXT) |
| `/chat` | POST | Chat with AI coach |
| `/clear` | POST | Clear session data |
| `/session/{id}/stats` | GET | Get session statistics |
| `/admin/cleanup` | POST | Manual cleanup (admin) |

### Example: Chat Request

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "X-ProView-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "user_message": "I want to prepare for a senior Python developer role",
    "history": []
  }'
```

**Response:**
```json
{
  "ai_response": {
    "interviewer_chat": "Great! Let's focus on senior Python concepts...",
    "is_correct": null,
    "score": null,
    "refined_explanation": null,
    "suggested_replies": [
      "I have 5 years of Python experience",
      "I specialize in Django and FastAPI"
    ]
  }
}
```

## 🔧 Configuration

Key environment variables in `app/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | **Required** - Groq API key |
| `PROVIEW_API_KEY` | - | API authentication key |
| `MODEL_NAME` | "llama-3.3-70b-versatile" | LLM model |
| `TEMPERATURE` | 0.3 | Response creativity |
| `EMBEDDING_MODEL` | "all-MiniLM-L6-v2" | Embedding model |
| `SESSION_TIMEOUT_HOURS` | 2 | Auto-cleanup interval |
| `MAX_FILE_SIZE_MB` | 10 | Max upload size |
| `RATE_LIMIT_REQUESTS` | 10 | Rate limit threshold |

## 📁 Project Structure

```
proview-ai/
├── app/
│   ├── config.py           # Configuration & environment
│   ├── llm_logic.py        # LangChain pipeline
│   ├── rag_storage.py      # Vector DB operations
│   ├── schemas.py          # Pydantic models
│   └── services.py         # Business logic
├── main.py                 # FastAPI application
├── streamlit_app.py        # Streamlit UI
├── requirements.txt        # Dependencies
└── .env                    # Environment variables
```

## 🐳 Docker Deployment

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/proview_db
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t proview-ai .
docker run -p 8000:8000 --env-file .env proview-ai
```

## 🧪 Testing

```python
# Test health check
curl http://localhost:8000/health

# Test with authentication
curl -X POST "http://localhost:8000/upload" \
  -H "X-ProView-Key: your_key" \
  -F "file=@resume.pdf" \
  -F "session_id=test-123"
```

## 🔒 Security Features

1. ✅ API key authentication on all endpoints
2. ✅ Session isolation prevents cross-user data access
3. ✅ Rate limiting prevents abuse
4. ✅ Input validation via Pydantic
5. ✅ File size and type restrictions
6. ✅ Automatic sensitive data cleanup

## 📊 Monitoring

Comprehensive logging implemented:
```python
INFO: Normal operations (uploads, chats, cleanups)
WARNING: Potential issues (unauthorized access)
ERROR: Failures (processing errors, DB errors)
```

Enable LangSmith tracing (optional):
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
```

## 🙏 Acknowledgments

- [LangChain](https://langchain.com) - LLM orchestration
- [Groq](https://groq.com) - Fast LLM inference
- [ChromaDB](https://www.trychroma.com) - Vector database
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
- [Streamlit](https://streamlit.io) - UI framework
- [HuggingFace](https://huggingface.co) - Embedding models

## 📄 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ by AI Engineers, for AI Engineers**