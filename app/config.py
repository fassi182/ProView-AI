import os
from dotenv import load_dotenv

load_dotenv()

class ProViewConfig:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # Interview engine LLM
    MODEL_NAME = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.7

    # High-performance, lightweight cloud embedding layout
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    @classmethod
    def validate(cls):
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is missing. Check your .env file.")
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("Supabase configuration keys are missing in your .env file.")