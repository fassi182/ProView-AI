#app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class ProViewConfig:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    MODEL_NAME = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.7

    @classmethod
    def validate(cls):
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is missing. Check your .env file.")