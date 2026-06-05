import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for VibeNote application."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "vibenote-secret-key-12345")
    
    # API Keys
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    
    # Hugging Face Token (for pyannote.audio)
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
    
    # App Settings
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")
    
    # File Upload Settings
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)) # 50 MB default
