# app/config.py
import os
from dotenv import load_dotenv
from typing import Set

load_dotenv()

class ProViewConfig:
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    PROVIEW_API_KEY = os.getenv("PROVIEW_API_KEY", "default-secret-key-change-me")

    # Model Configuration
    MODEL_NAME = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.3

    # LangChain Tracing
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT = "ProView-AI-Production"

    # Storage Configuration
    PERSIST_DIRECTORY = "./proview_db"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    # Security & Cleanup
    SESSION_TIMEOUT_HOURS = 2
    MAX_FILE_SIZE_MB = 10
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}
    
    # CORS Configuration
    ALLOWED_ORIGINS = os.getenv(
        "ALLOWED_ORIGINS", 
        "http://localhost:8501,http://127.0.0.1:8501"
    ).split(",")

    # Rate Limiting
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW_SECONDS = 60
    
    # File Upload
    TEMP_UPLOAD_DIR = "./temp_uploads"
    
    # Chat Configuration
    MAX_HISTORY_LENGTH = 10
    MAX_MESSAGE_LENGTH = 5000

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY must be set in environment variables")
        if cls.PROVIEW_API_KEY == "default-secret-key-change-me":
            print("⚠️ WARNING: Using default PROVIEW_API_KEY. Change this in production!")
        
        # Create temp directory if it doesn't exist
        os.makedirs(cls.TEMP_UPLOAD_DIR, exist_ok=True)
        os.makedirs(cls.PERSIST_DIRECTORY, exist_ok=True)
        
        # Validate numeric configs
        if cls.MAX_FILE_SIZE_MB <= 0:
            raise ValueError("MAX_FILE_SIZE_MB must be positive")
        if cls.SESSION_TIMEOUT_HOURS <= 0:
            raise ValueError("SESSION_TIMEOUT_HOURS must be positive")