#app/config.py
import os
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()

class ProViewConfig:
    """
    Configuration that works both locally and on Streamlit Cloud
    Priority: Streamlit secrets > Environment variables > Defaults
    """
    
    @staticmethod
    def _get_secret(key: str, default=None):
        """
        Get configuration value from multiple sources
        Priority: streamlit secrets > env vars > default
        """
        try:
            # Try Streamlit secrets first (when deployed)
            import streamlit as st
            if hasattr(st, 'secrets') and key in st.secrets:
                return st.secrets[key]
        except (ImportError, FileNotFoundError, KeyError):
            pass
        
        # Fallback to environment variables
        return os.getenv(key, default)
    
    # API Keys
    @classmethod
    def get_groq_api_key(cls):
        key = cls._get_secret("GROQ_API_KEY")
        if not key:
            raise ValueError(
                "GROQ_API_KEY not found. "
                "Set it in .env (local) or Streamlit secrets (cloud)"
            )
        return key
    
    @classmethod
    def get_proview_api_key(cls):
        return cls._get_secret("PROVIEW_API_KEY", "default-secret-key-change-me")
    
    @classmethod
    def get_langchain_api_key(cls):
        return cls._get_secret("LANGCHAIN_API_KEY")
    
    # Model Configuration
    MODEL_NAME = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.3
    
    # LangChain Tracing
    @classmethod
    def get_langchain_tracing(cls):
        return cls._get_secret("LANGCHAIN_TRACING_V2", "false")
    
    LANGCHAIN_PROJECT = "ProView-AI-Production"
    
    # Storage Configuration
    PERSIST_DIRECTORY = "./proview_db"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    
    # Security & Cleanup
    SESSION_TIMEOUT_HOURS = 2
    MAX_FILE_SIZE_MB = 10
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW_SECONDS = 60
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        # This will raise if GROQ_API_KEY is missing
        cls.get_groq_api_key()
        
        if cls.get_proview_api_key() == "default-secret-key-change-me":
            import logging
            logging.warning(
                "⚠️ WARNING: Using default PROVIEW_API_KEY. "
                "Change this in production!"
            )
    
    @classmethod
    def setup_environment(cls):
        """Setup environment variables for LangChain and other libraries"""
        os.environ["GROQ_API_KEY"] = cls.get_groq_api_key()
        
        langchain_key = cls.get_langchain_api_key()
        if langchain_key:
            os.environ["LANGCHAIN_API_KEY"] = langchain_key
            os.environ["LANGCHAIN_TRACING_V2"] = cls.get_langchain_tracing()
            os.environ["LANGCHAIN_PROJECT"] = cls.LANGCHAIN_PROJECT