# VibeNote — Real-Time Sentiment & AI Meeting Analytics

VibeNote is a next-generation real-time meeting analysis platform. It captures conversation audio (via direct microphone streaming, file uploads, or Chrome Extension tab audio capture), transcribes it in real-time, extracts key topics, performs emotional tone tracking, and generates polished executive summary reports tailored to specific industry verticals (Manufacturing, Construction, and Financial Services).

---

## 📂 Project Structure

```text
vibenote/
├── backend/
│   ├── app.py                # Flask app with Flask-SocketIO (eventlet) & CORS
│   ├── config.py             # Configuration system loading env variables
│   ├── requirements.txt      # Python dependencies (CPU-only PyTorch & Whisper)
│   └── .env.example          # Template for Gemini, Groq, and HF API keys
├── frontend/
│   ├── index.html            # Premium glassmorphic analytics dashboard UI
│   ├── app.js                # SocketIO client, MediaRecorder pipeline, & Chart.js
│   └── styles.css            # Dark theme, layout grids, and animations
├── extension/
│   ├── manifest.json         # Chrome Extension Manifest V3 config
│   ├── content.js            # Message relay bridge in the browser tab context
│   ├── background.js         # Service Worker & Popup Controller dual script
│   └── popup.html            # Extension popup capture control UI
├── docker-compose.yml        # Docker service definition for CPU-only execution
└── README.md                 # Project guide and execution documentation
```

---

## 🛠️ Tech Stack & Design

- **Backend**: Python 3.11, Flask, Flask-SocketIO (backed by `eventlet` for high-concurrency real-time WebSocket communication), Flask-CORS.
- **Audio & AI Processing**:
  - **Whisper**: Local OpenAI Whisper (`tiny` model, loaded lazily on CPU) for high-performance offline transcription.
  - **LLM Integrations**: Google Gemini (`gemini-1.5-flash`) or Groq (`llama3-8b-8192`) for extracting emotional spectrums, topic insights, and structuring markdown reports.
  - **Graceful Fallbacks**: If API keys are missing or CPU hardware is constrained, the backend triggers an advanced industry-specific dialogue and analytics simulator. This lets you demo the entire live dashboard experience instantly out-of-the-box.
- **Frontend**: Pure HTML5, CSS Grid/Flexbox (Premium glassmorphic dark design, micro-animations, custom scrollbars), Chart.js (for the doughnut-shaped Emotion Spectrum), Socket.IO Client.
- **Chrome Extension**: Manifest V3 compliant. Uses `chrome.tabCapture` to capture audio from active browser tabs (Google Meet, Teams, Zoom Web, Youtube, etc.) and routes it dynamically to the dashboard using secure cross-context window messaging.

---

## 🚀 Installation & Setup

### Option 1: Running Locally (Recommended for Development)

#### 1. Setup Backend Environment
Make sure you have Python 3.11 installed.

```bash
# Navigate to backend
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies (CPU index URL is pre-configured for PyTorch)
pip install -r requirements.txt
```

#### 2. Install FFmpeg (Required for audio decoding)
Whisper and audio processing libraries require `ffmpeg` to decode webm/opus files:
- **On Windows**: Open a PowerShell window and run:
  ```powershell
  winget install FFmpeg
  ```
  *(Remember to restart your terminal window after installation so python registers the new PATH).*
- **On macOS**: Run `brew install ffmpeg`.
- **On Linux (Ubuntu/Debian)**: Run `sudo apt update && sudo apt install ffmpeg`.

#### 3. Hugging Face Setup (Required for Speaker Diarization)
VibeNote uses Pyannote for speaker diarization. Since Pyannote models are gated, you must accept their terms:
1. Log in to [Hugging Face](https://huggingface.co/).
2. Visit both of these repositories, fill out the basic form, and click **"Agree and access repository"**:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Create a **Read** access token by going to your [Hugging Face Token Settings](https://huggingface.co/settings/tokens).
4. Copy the token (starts with `hf_...`).

#### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
- `GEMINI_API_KEY`: Your Gemini API Key from Google AI Studio.
- `GROQ_API_KEY`: Your Groq API Key from Groq Console.
- `HF_TOKEN`: Your Hugging Face access token (generated in Step 3).

#### 5. Run Backend
```bash
python app.py
```
The server will start on `http://localhost:5000`. On the very first run, it will automatically download the Whisper and Pyannote weights to your machine (approx. 500MB total). This is a one-time setup.

#### 6. Run Frontend
Simply open `frontend/index.html` in your web browser (or serve it via any static server, e.g. VS Code Live Server).

---

### Option 2: Running via Docker Compose

Docker Compose automatically pulls a Python 3.11 image, mounts the backend directory, installs the required system packages (`libsndfile1` for audio file support, `ffmpeg`), installs python requirements, and spins up the server.

```bash
# Build and run the container
docker-compose up --build
```
The Flask-SocketIO backend container starts on port `5000` with hot-reloading enabled.

---

## 🔌 Setting up the Chrome Extension

The VibeNote Chrome Extension captures audio from tabs (e.g. video conferencing tabs) and streams it to the VibeNote dashboard.

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle switch in the top-right corner).
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `extension/` directory of the VibeNote project.
5. The extension icon will now appear in your browser. Pin it for quick access!

---

## 📖 How to Use

1. **Configure Vertical**: Select your industry (Manufacturing, Construction, Financial Services) in the dashboard or extension.
2. **Start a Live Session**:
   - **Direct Microphone**: Click **Start Live Session** on the dashboard. Grant microphone permission. Speak, and watch real-time transcript bubbles, topics, and emotion charts update dynamically. Click **Stop Live Session** to compile the final executive report.
   - **Tab Capture (Chrome Extension)**: Open a tab with audio (like a video call or YouTube). Click the VibeNote Extension icon, input the server URL, select your industry, and click **Capture Tab Audio**. The extension will open a connection, sync with the dashboard tab, start streaming, and display real-time metrics on the dashboard tab. Click **Stop Capturing** inside the extension to finalize the session.
3. **Upload Recording**: Click **Upload Recording** on the dashboard, select any audio file (`.wav`, `.mp3`, `.m4a`), and the backend will process the full file, transcribing and summarizing it in seconds.
