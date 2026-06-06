import os
import sys
from dotenv import load_dotenv

# Resolve absolute paths to support execution from any directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
sys.path.append(backend_dir)

# Load .env file from root
env_path = os.path.join(root_dir, '.env')
if os.path.exists(env_path):
    print(f"Loading environment from: {env_path}")
    load_dotenv(dotenv_path=env_path)
else:
    print("Warning: No .env file found at root. Using system environment variables.")
    load_dotenv()

from config import Config
from app import app, socketio
import gemini_client
import knowledge_base

def run_checklist():
    print("\n" + "="*50)
    print("VIBENOTE SERVER STARTUP CHECKLIST")
    print("="*50)
    
    # 1. API Keys validation
    gemini_key = os.getenv("GEMINI_API_KEY") or Config.GEMINI_API_KEY
    groq_key = os.getenv("GROQ_API_KEY") or Config.GROQ_API_KEY
    hf_token = os.getenv("HF_TOKEN") or Config.HF_TOKEN
    
    if gemini_key:
        print("  [✓] Gemini API Key: Configured")
    else:
        print("  [!] Gemini API Key: MISSING (Fallback options will be limited)")
        
    if groq_key:
        print("  [✓] Groq API Key: Configured (Primary LLM ready)")
    else:
        print("  [!] Groq API Key: MISSING (VibeNote will default to Gemini for analysis)")
        
    if hf_token:
        print("  [✓] Hugging Face Token: Configured (Diarization pipeline ready)")
    else:
        print("  [!] Hugging Face Token: MISSING (Diarization model authorization might fail)")

    # 2. Industry Knowledge Base
    if len(knowledge_base.JARGON_DB) >= 3:
        print("  [✓] Industry Jargon Database: Loaded (Manufacturing, Construction, Financial Services)")
    else:
        print("  [!] Industry Jargon Database: Verification failed")

    # 3. Port & Debug Configurations
    print(f"  [✓] Host Binding: 0.0.0.0:{Config.PORT}")
    print(f"  [✓] Debug Mode: {Config.DEBUG}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_checklist()
    print("Starting Flask-SocketIO application...")
    socketio.run(app, host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
