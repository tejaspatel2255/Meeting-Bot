# VibeNote — Real-Time Sentiment & AI Meeting Analytics

VibeNote is a real-time meeting analysis platform. It captures conversation audio (via Chrome Extension tab audio capture or file uploads), transcribes it, extracts key topics, performs emotional tone tracking, and generates polished executive summary reports tailored to specific industry verticals (Manufacturing, Construction, and Financial Services).

---

## 🚀 Setup in 5 Steps

Follow these five steps to get the complete VibeNote pipeline running on your machine:

### 1. Clone the Repository
Clone the codebase to your local machine:
```bash
git clone https://github.com/tejaspatel2255/Meeting-Bot.git
cd Meeting-Bot
```

### 2. Create the `.env` Configuration File
Create a `.env` file in the root directory and add your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
HF_TOKEN=your_hugging_face_token_here
```
> [!NOTE]
> - **Gemini API Key**: Obtain from Google AI Studio.
> - **Groq API Key**: Obtain from Groq Console.
> - **HF Token**: Create a Read token on Hugging Face (Required for Pyannote speaker diarization). Ensure you accept terms for `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`.

### 3. Install Python Dependencies
Create a virtual environment and install dependencies:
```bash
# Navigate to the backend directory
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```
*(Make sure `ffmpeg` is installed on your system and is accessible in your system PATH environment variable).*

### 4. Start the Server
Run the single entry point script to boot the backend:
```bash
python run.py
```
This loads your `.env`, runs a quick configuration checklist, and runs the Socket.IO server on `http://localhost:5000`.

### 5. Install the Chrome Extension
Load the extension in your browser:
1. Open Google Chrome and go to `chrome://extensions/`.
2. Toggle **"Developer mode"** ON in the top-right corner.
3. Click **"Load unpacked"** in the top-left corner and select the `extension/` folder in the project root.
4. Open `frontend/index.html` directly in your browser.

---

## 📖 How to Use

VibeNote operates in two modes:

### Mode A: Live Tab Capture (Real-Time)
Stream meetings directly from browser tabs (Google Meet, Zoom, Teams):
1. Input your target meeting URL and select the Industry vertical in the dashboard.
2. Click **Start Live Session**.
3. Open your meeting tab, click the VibeNote extension icon in the Chrome toolbar, and click **Start Capturing** (allow tab capture permission).
4. The extension captures and streams 1-second audio chunks to the backend, which feeds real-time transcript lines, sentiment indexes, and topics to the dashboard.
5. Click **Stop Capturing** in the extension popup to stop the stream, and click **End Meeting** on the dashboard to trigger the final executive report.

### Mode B: Batch File Upload (Asynchronous)
Analyze pre-recorded meeting audio files:
1. Select the Industry vertical on the dashboard.
2. Click **Upload Recording** and choose your audio file (`.wav`, `.mp3`, `.m4a`, etc.).
3. The dashboard will show a loading progress bar.
4. The backend processes the audio on a background thread (`transcribe_file` → `diarize` → `assign_speakers`), runs analysis, and streams the updates to the dashboard as they compile.
5. Once complete, the final compiled summary report displays at the bottom automatically.

---

## 📊 API & Free Tier Limits

- **Google Gemini API**:
  - **Free Tier limits**: 15 requests per minute (RPM) and 1,500 requests per day (RPD) on the `gemini-2.5-flash` model.
- **Groq API**:
  - **Free Tier limits**: 14,400 requests per day (RPD) on the `llama-3.1-8b-instant` model.
- **Hugging Face / Pyannote**:
  - Diarization pipelines are free but require gating approval and token authentication (`HF_TOKEN`).

---

## 🛠️ Troubleshooting

- **Whisper Transcription is Too Slow**:
  - If processing takes too long, configure `transcriber.py` to use the `tiny` or `base` model instead of `small` (e.g. `whisper.load_model("tiny", device="cpu")`).
- **Gemini Rate Limit Exceeded**:
  - VibeNote has built-in primary/secondary failover. If Gemini hits quota limits, the Groq API (`llama-3.1-8b-instant`) takes over automatically to process transcription lines and summaries.
- **No Audio Captured (Silent feed)**:
  - Ensure you click the **"Share tab audio"** checkbox in the Chrome tab capture sharing permission dialog when activating the extension.
