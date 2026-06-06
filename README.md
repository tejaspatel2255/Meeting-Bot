# VibeNote — Real-Time Sentiment & AI Meeting Analytics

VibeNote is a real-time meeting analysis platform. It captures conversation audio (via direct microphone streaming, Chrome Extension tab audio capture, batch file uploads, or **headless meeting bots**), transcribes it, extracts key topics, performs emotional tone tracking, and generates polished executive summary reports tailored to specific industry verticals (Manufacturing, Construction, and Financial Services).

---

## 📂 Project Structure

```text
vibenote/
├── backend/
│   ├── app.py                # Flask app with Flask-SocketIO & CORS
│   ├── config.py             # Configuration system loading env variables
│   ├── requirements.txt      # Python dependencies (Whisper, Playwright, CPU PyTorch)
│   ├── run.py                # Unified app entry point and configuration checklist
│   ├── test_pipeline.py      # automated pipeline test suite
│   ├── bot/                  # Autonomous Headless Meeting Bot (Phase 9)
│   │   ├── base_bot.py       # Abstract Base Bot class with SocketIO emitters
│   │   ├── bot_launcher.py   # Threaded background bot manager
│   │   ├── meet_bot.py       # Playwright Google Meet bot
│   │   ├── zoom_bot.py       # Playwright Zoom web client bot
│   │   ├── teams_bot.py      # Playwright Teams web client bot
│   │   └── xvfb_manager.py   # Xvfb headless display buffer manager for Linux
│   └── .env.example          # Environment variables template
├── frontend/
│   ├── index.html            # Neon-dark styled glassmorphic dashboard UI
│   ├── app.js                # SocketIO client, MediaRecorder pipelines, & Chart.js
│   └── styles.css            # Dark theme, layout grids, and animations
├── extension/
│   ├── manifest.json         # Chrome Extension Manifest V3 config
│   ├── content.js            # Message relay bridge in the browser tab context
│   ├── background.js         # Service Worker & Popup Controller
│   └── popup.html            # Extension popup capture control UI
├── docker-compose.yml        # Docker service definition with XVFB and Playwright support
└── README.md                 # Project setup and usage instructions
```

---

## 🛠️ Tech Stack & Design

- **Backend**: Python 3.11/3.13, Flask, Flask-SocketIO (backed by `eventlet` for real-time WebSocket communication), Flask-CORS.
- **Audio & AI Processing**:
  - **Whisper**: Local OpenAI Whisper (`tiny` or `base` model on CPU) for high-performance offline transcription.
  - **LLM Integrations**: Google Gemini (`gemini-1.5-flash`) or Groq (`llama-3.1-8b-instant`) for extracting emotional spectrums and structuring markdown reports.
  - **Graceful Fallbacks**: Automatically fails over to Groq if Gemini hits quota limits, and uses a deterministic local knowledge base for industry-specific jargon scanning.
- **Headless Meeting Bot**: Playwright-based background bots that automatically join calls (Google Meet, Zoom, Teams), bypass user prompts, intercept WebRTC AudioContext streams, mix incoming channels, and stream audio chunks to the server.
- **Frontend**: Pure HTML5, CSS Grid/Flexbox, Chart.js (for the Sentiment Timeline), Socket.IO Client.

---

## 🚀 Setup & Execution

### 1. Configure Secrets (`.env`)
Create a `.env` file inside `backend/` (`backend/.env`) with your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
HF_TOKEN=your_hugging_face_token_here

# Bot configuration
DISPLAY=:99
BOT_NAME=VibeNote Bot
```
> [!IMPORTANT]
> The Hugging Face Token (`HF_TOKEN`) is required for the Pyannote speaker diarization models. Make sure you accept the repository terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1).

---

### Option A: Run via Docker Compose (Recommended for Bot support)
The Docker Compose environment comes pre-configured with Xvfb (Virtual Framebuffer) and Pulseaudio required to render headless browser audio streams on Linux:

1. Build and run the containers:
   ```bash
   docker-compose up --build
   ```
2. Open `frontend/index.html` directly in Google Chrome.
3. Submit a meeting URL (e.g. Google Meet, Zoom Web Client, or Teams link) and select your industry vertical. The backend will spin up the virtual bot in the background to join, record, and analyze your meeting.

---

### Option B: Local Setup (Windows / macOS)

1. **Install Python dependencies**:
   ```bash
   cd backend
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   
   pip install -r requirements.txt
   playwright install chromium
   ```
2. **Start the backend server**:
   ```bash
   python run.py
   ```
3. **Open the Dashboard**:
   Open `frontend/index.html` in your browser.

---

## 🔌 Installing the Chrome Extension
If you prefer to stream audio directly from your active browser tab instead of using the headless bot:
1. Open Google Chrome and go to `chrome://extensions/`.
2. Toggle **Developer mode** ON (top-right corner).
3. Click **Load unpacked** (top-left) and select the `extension/` directory.
4. Input the server URL `http://localhost:5000` in the extension popup and click **Capture Tab Audio**.

---

## 🔒 Safety & Git Push

The `.gitignore` is pre-configured to ensure no secrets or API keys are ever committed to your repository:
- It ignores all virtual environments (`venv/`, `env/`).
- It ignores `.env` files and developer configurations (`.env`, `.env.*`).
- It excludes Playwright browser caches and build directories.

You can safely push your code to GitHub:
```bash
git add .
git commit -m "Add headless meeting bot integration for Zoom, Meet, and Teams"
git push origin main
```
