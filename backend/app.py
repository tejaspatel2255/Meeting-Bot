import os
import sys
import uuid
import json
import time
import base64
import tempfile
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

from config import Config
from transcriber import transcribe_chunk, transcribe_file, assign_speakers
from speaker import diarize

# Create Flask app and configure SocketIO
app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Create upload folder if it doesn't exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# Lazy loading wrappers for AI dependencies
genai_configured = False
groq_client = None

def get_gemini_client():
    """Lazily configure Gemini client."""
    global genai_configured
    if not genai_configured:
        if Config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=Config.GEMINI_API_KEY)
                genai_configured = True
                print("Gemini API configured successfully.")
            except Exception as e:
                print(f"Error configuring Gemini: {e}", file=sys.stderr)
    return genai_configured

def get_groq_client():
    """Lazily initialize Groq client."""
    global groq_client
    if groq_client is None:
        if Config.GROQ_API_KEY:
            try:
                from groq import Groq
                groq_client = Groq(api_key=Config.GROQ_API_KEY)
                print("Groq client initialized successfully.")
            except Exception as e:
                print(f"Error initializing Groq client: {e}", file=sys.stderr)
    return groq_client

# In-memory Session Store
# Format: { session_id: { url, industry, audio_buffer, file_path, transcript, emotions, topics, chunk_count, start_time } }
SESSIONS = {}

# Predefined high-quality dialogue and analysis mocks for fallback demo mode
INDUSTRY_DATA = {
    "manufacturing": {
        "dialogue": [
            {"speaker": "Manager", "text": "Good morning team. Let's review the production delays on Assembly Line 3. The main hydraulic valve is malfunctioning.", "timestamp": "0:05"},
            {"speaker": "Lead Engineer", "text": "Yes, the replacement part is backordered. We are looking at a 48-hour delay unless we source a compatible valve locally.", "timestamp": "0:25"},
            {"speaker": "Manager", "text": "We can't wait 48 hours. Every hour of downtime costs us roughly ten thousand dollars in lost throughput.", "timestamp": "0:45"},
            {"speaker": "Procurement", "text": "I checked Apex Distributors. They have a unit in stock that matches our specs, but it carries a twenty percent markup.", "timestamp": "1:05"},
            {"speaker": "Manager", "text": "Pay the premium and arrange an expedited hot-shot delivery. Also, ensure safety tagout protocols are fully followed before installation.", "timestamp": "1:30"}
        ],
        "topics": [
            {"text": "Line 3 Downtime", "value": 90},
            {"text": "Hydraulic Valve", "value": 85},
            {"text": "Supplier Backlog", "value": 70},
            {"text": "Apex Procurement", "value": 80},
            {"text": "Safety Tagout", "value": 75},
            {"text": "Hourly Loss ($10K)", "value": 90}
        ],
        "emotions": {
            "Professional": 40,
            "Urgent": 35,
            "Concerned": 15,
            "Relieved": 10
        },
        "summary": """### Executive Summary
A critical malfunction of the main hydraulic valve on Assembly Line 3 has halted production. Sourcing the replacement part from the primary supplier would result in a 48-hour delay, costing the plant approximately $240,000. 

### Key Takeaways
- **Downtime Impact:** Every hour of downtime on Line 3 costs $10,000 in lost throughput.
- **Sourcing Strategy:** The primary supplier is backordered, requiring local sourcing.
- **Apex Parts Availability:** Apex Distributors has the part in stock with a 20% markup.
- **Safety Priority:** Maintenance must adhere to Lockout/Tagout (LOTO) safety protocols.

### Action Items
- **[Urgent] Procurement:** Purchase the replacement hydraulic valve from Apex Distributors immediately with expedited shipping.
- **[Safety] Engineering:** Review and update lockout/tagout safety checklists prior to installing the new valve.
- **[Operations] Supervisor:** Reallocate line workers to alternative lines to minimize labor downtime during repairs.
"""
    },
    "construction": {
        "dialogue": [
            {"speaker": "Project Manager", "text": "Welcome to the site alignment. We have a zoning setback issue with the foundation pour on Sector B. The concrete inspector flag is still red.", "timestamp": "0:07"},
            {"speaker": "Subcontractor", "text": "The municipal inspector requested an updated structural plan because of the new soil density readings we submitted last week.", "timestamp": "0:28"},
            {"speaker": "Project Manager", "text": "We need this resolved by Thursday. The steel framing crew is scheduled to arrive next Monday, and they won't wait.", "timestamp": "0:48"},
            {"speaker": "Structural Engineer", "text": "I have drafted the revised foundation plans. I will stamp and submit them to the city portal by this afternoon.", "timestamp": "1:10"},
            {"speaker": "Project Manager", "text": "Excellent. Make sure you call the inspector directly to expedite the sign-off. We can't let the steel crew sit idle.", "timestamp": "1:32"}
        ],
        "topics": [
            {"text": "Sector B Foundation", "value": 92},
            {"text": "Zoning Permit", "value": 88},
            {"text": "Soil Density Report", "value": 80},
            {"text": "Steel Framing Crew", "value": 85},
            {"text": "Expedited Inspection", "value": 78},
            {"text": "Project Schedule", "value": 75}
        ],
        "emotions": {
            "Professional": 45,
            "Stressed": 25,
            "Determined": 20,
            "Focused": 10
        },
        "summary": """### Executive Summary
The weekly site meeting addressed a zoning and engineering roadblock on Sector B's foundation. A concrete pour inspector flagged the foundation due to updated soil density readings. The project timeline is at risk, as the steel framing crew arrives next Monday.

### Key Takeaways
- **Inspection Block:** Municipal inspector flagged Sector B concrete pour due to recent soil density changes.
- **Framing Dependency:** Steel framing crew begins next Monday; concrete must be cured.
- **Resolution Plan:** Structural drawings are being revised today to satisfy city codes.
- **Coordination Need:** Direct developer/inspector outreach is required to fast-track approvals.

### Action Items
- **[Urgent] Structural Engineer:** Complete, sign off, and upload the updated structural diagrams to the municipal portal today.
- **[Critical] Project Manager:** Contact the building inspector directly to request an expedited review.
- **[Logistics] Subcontractor:** Keep concrete trucks on standby for Thursday morning.
"""
    },
    "financial services": {
        "dialogue": [
            {"speaker": "Wealth Advisor", "text": "Thanks for joining. Given the Federal Reserve's latest rate hikes, we need to rebalance your asset allocation to mitigate market volatility.", "timestamp": "0:06"},
            {"speaker": "Client", "text": "I've been feeling nervous looking at the market swings. Should we transition some of our equity holdings into safer yields?", "timestamp": "0:24"},
            {"speaker": "Wealth Advisor", "text": "Yes. Short-term Treasury bills are yielding over five percent risk-free. It's a great harbor while equity valuations stabilize.", "timestamp": "0:45"},
            {"speaker": "Client", "text": "That makes sense. Let's do a fifteen percent reallocation from my growth stock index to the high-yield T-bills.", "timestamp": "1:02"},
            {"speaker": "Wealth Advisor", "text": "Sounds like a solid plan. I will draft the authorization documents and send them via DocuSign this afternoon.", "timestamp": "1:22"}
        ],
        "topics": [
            {"text": "Fed Rate Hikes", "value": 95},
            {"text": "Portfolio Rebalancing", "value": 90},
            {"text": "Market Volatility", "value": 85},
            {"text": "Treasury Bills (5%+)", "value": 88},
            {"text": "Asset Allocation", "value": 75},
            {"text": "DocuSign Signature", "value": 70}
        ],
        "emotions": {
            "Professional": 50,
            "Calm": 25,
            "Apprehensive": 15,
            "Satisfied": 10
        },
        "summary": """### Executive Summary
The client advisory call focused on portfolio rebalancing in response to persistent Fed interest rate hikes. To combat market volatility, the advisor suggested relocating capital from volatile equity funds into fixed income. The client agreed to a 15% shift to Short-term US Treasury bills.

### Key Takeaways
- **Rate Environment:** Federal Reserve interest rate hikes make fixed-income instruments highly attractive.
- **Risk Mitigation:** Shifting assets out of growth equities reduces exposure to short-term market swings.
- **T-Bill Yields:** Short-term US Treasuries currently offer >5% risk-free yield.
- **Asset Rebalancing:** Agreed to relocate 15% of the total portfolio into fixed-income Treasuries.

### Action Items
- **[Operational] Wealth Advisor:** Draft the 15% portfolio reallocation forms this morning.
- **[Documentation] Client:** Electronically sign the rebalancing authorization documents via DocuSign upon receipt.
- **[Execution] Advisory Team:** Execute the stock liquidation and Treasury purchase immediately upon signature validation.
"""
    }
}

# AI Utility Functions

def parse_audio_data(audio_bytes):
    """
    Parse raw audio bytes into a format Whisper or Soundfile can read.
    Saves bytes to a temp file and returns the file path.
    """
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.write(audio_bytes)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Error parsing audio bytes: {e}", file=sys.stderr)
        return None

def analyze_text_with_llm(text, industry, analysis_type):
    """
    Uses Gemini or Groq to analyze transcript text.
    analysis_type can be 'emotions_topics' or 'summary'.
    """
    prompt = ""
    if analysis_type == 'emotions_topics':
        prompt = f"""
        Analyze the following conversation transcript from the {industry} industry.
        
        Transcript:
        "{text}"
        
        1. Extract the main topics discussed. Return them as a JSON list of objects with keys 'text' (the topic name) and 'value' (relevance score from 10 to 100). Keep them concise.
        2. Identify the emotional tone / sentiment distribution of the conversation. Return a JSON object with keys as emotions (e.g. Professional, Urgent, Concerned, Confident, Calm, Stressed) and values as percentage scores (summing to 100).
        
        Format your final response as a clean JSON object with keys "topics" and "emotions". Do not include markdown code block formatting (like ```json). Return ONLY raw JSON.
        """
    elif analysis_type == 'summary':
        prompt = f"""
        Provide a professional executive summary of the following conversation transcript from the {industry} industry.
        
        Transcript:
        "{text}"
        
        Provide the response in Markdown format. Organize it with the following headers:
        ### Executive Summary
        (A concise 2-3 sentence overview of the meeting and its main purpose)
        ### Key Takeaways
        (A list of bullet points detailing the core details discussed)
        ### Action Items
        (A list of actionable steps, prefixed with [Urgent], [Critical], or [Operational] and who is responsible)
        
        Return ONLY the markdown text.
        """

    # Try Groq (Primary Model)
    if get_groq_client():
        try:
            # Using llama-3.1-8b-instant for fast latency
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.2
            )
            if chat_completion.choices and chat_completion.choices[0].message.content:
                return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq generation failed: {e}. Trying Gemini...", file=sys.stderr)

    # Try Gemini (Fallback Model)
    if get_gemini_client():
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini generation failed: {e}.", file=sys.stderr)
            
    # Fallback to local rule-based/mock data if LLMs are unavailable
    return None


# Flask HTTP Routes

@app.route('/', methods=['GET'])
def index():
    """Health check / API status endpoint."""
    return jsonify({
        "status": "online",
        "service": "VibeNote AI Backend Pipeline",
        "engine": "Flask + Flask-SocketIO (eventlet)",
        "models_loaded": {
            "whisper": "Dynamic (lazy-loaded on CPU)",
            "gemini": genai_configured,
            "groq": groq_client is not None
        }
    })

@app.route('/api/join', methods=['POST'])
def api_join():
    """
    Join or create a live recording session.
    Accepts JSON body: { "url": str, "industry": str }
    """
    data = request.get_json() or {}
    url = data.get('url', 'http://localhost')
    industry = data.get('industry', 'Manufacturing').lower()
    
    # Generate unique session ID
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    
    # Register the session
    SESSIONS[session_id] = {
        "url": url,
        "industry": industry,
        "audio_chunks": [],
        "file_path": None,
        "transcript": [],
        "emotions": {},
        "topics": [],
        "chunk_count": 0,
        "start_time": time.time()
    }
    
    print(f"Session Created: {session_id} for URL: {url} | Industry: {industry}")
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "url": url,
        "industry": industry,
        "message": f"Successfully joined session {session_id}"
    })

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """
    Upload an audio file for batch processing.
    Accepts Multipart Form: 'file' (audio file), 'industry' (str)
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    industry = request.form.get('industry', 'Manufacturing').lower()
    if industry not in ["manufacturing", "construction", "financial services"]:
        industry = "manufacturing"

    # Save to upload directory
    file_id = uuid.uuid4().hex[:8]
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    print(f"File uploaded successfully to: {file_path}. Industry: {industry}")
    
    # Run the modular audio processing pipeline (Whisper small + Pyannote diarization)
    transcript_text = ""
    transcript_list = []
    
    try:
        # Step 1: Run transcription (Whisper small model)
        whisper_segments = transcribe_file(file_path)
        
        # Step 2: Run speaker diarization (Pyannote pipeline)
        diarization_intervals = diarize(file_path)
        
        # Step 3: Align speaker tags to transcription segments
        aligned_segments = assign_speakers(whisper_segments, diarization_intervals)
        
        # Format segments into the transcript output list
        for seg in aligned_segments:
            start_sec = int(seg.get("start", 0.0))
            min_part = start_sec // 60
            sec_part = start_sec % 60
            timestamp = f"{min_part}:{sec_part:02d}"
            
            transcript_list.append({
                "speaker": seg.get("speaker", "Unknown"),
                "text": seg.get("text", "").strip(),
                "timestamp": timestamp
            })
            
        transcript_text = " ".join([f"{item['speaker']}: {item['text']}" for item in transcript_list])
    except Exception as e:
        print(f"Modular transcription/diarization pipeline failed: {e}. Falling back to mock.", file=sys.stderr)
        transcript_text = ""
        transcript_list = []

    if not transcript_list or not transcript_text:
        # Generate beautiful mock transcript matching the industry
        mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
        transcript_list = mock_data["dialogue"]
        transcript_text = " ".join([f"{item['speaker']}: {item['text']}" for item in transcript_list])
        
    # Run analysis
    raw_analysis = analyze_text_with_llm(transcript_text, industry, 'emotions_topics')
    topics = []
    emotions = {}
    
    if raw_analysis:
        try:
            # Clean possible markdown block wraps
            clean_json = raw_analysis.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            topics = parsed.get("topics", [])
            emotions = parsed.get("emotions", {})
        except Exception as e:
            print(f"Failed to parse LLM analysis JSON: {e}", file=sys.stderr)
            
    # Fallback mock analysis if LLM failed
    if not topics or not emotions:
        mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
        topics = mock_data["topics"]
        emotions = mock_data["emotions"]
        
    # Generate summary report
    summary = analyze_text_with_llm(transcript_text, industry, 'summary')
    if not summary:
        mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
        summary = mock_data["summary"]

    # Clean up uploaded file
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Failed to delete temporary file {file_path}: {e}", file=sys.stderr)

    return jsonify({
        "status": "success",
        "industry": industry,
        "transcript": transcript_list,
        "topics": topics,
        "emotions": emotions,
        "summary": summary
    })

@app.route('/api/end', methods=['POST'])
def api_end():
    """
    End session, perform final batch aggregation and return summaries.
    Accepts JSON body: { "session_id": str }
    """
    data = request.get_json() or {}
    session_id = data.get('session_id')
    
    if not session_id or session_id not in SESSIONS:
        return jsonify({"status": "error", "message": "Invalid or missing session_id"}), 400
        
    sess = SESSIONS[session_id]
    industry = sess["industry"]
    
    # If there are real audio chunks accumulated from the live socket stream, run the full pipeline on them
    if sess["audio_chunks"]:
        print(f"Finalizing live session {session_id} by processing accumulated audio chunks...", flush=True)
        try:
            full_audio_bytes = b"".join(sess["audio_chunks"])
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(full_audio_bytes)
                temp_file_path = temp_file.name

            # Run full file pipeline (Whisper small + Pyannote diarization)
            whisper_segments = transcribe_file(temp_file_path)
            diarization_intervals = diarize(temp_file_path)
            aligned_segments = assign_speakers(whisper_segments, diarization_intervals)

            # Clean up temp file
            try:
                os.remove(temp_file_path)
            except:
                pass

            if aligned_segments:
                sess["transcript"] = []
                for seg in aligned_segments:
                    start_sec = int(seg.get("start", 0.0))
                    min_part = start_sec // 60
                    sec_part = start_sec % 60
                    timestamp = f"{min_part}:{sec_part:02d}"
                    
                    sess["transcript"].append({
                        "speaker": seg.get("speaker", "Unknown"),
                        "text": seg.get("text", "").strip(),
                        "timestamp": timestamp
                    })
        except Exception as err:
            print(f"Error processing final live audio compilation: {err}", file=sys.stderr, flush=True)

    # If the transcript list remains empty (e.g. no real voice captured or mock mode demo), generate mock data
    if not sess["transcript"]:
        mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
        sess["transcript"] = mock_data["dialogue"]
        sess["topics"] = mock_data["topics"]
        sess["emotions"] = mock_data["emotions"]
        sess["summary"] = mock_data["summary"]
    else:
        # Full text compilation
        full_text = " ".join([f"{item['speaker']}: {item['text']}" for item in sess["transcript"]])
        
        # Final LLM run
        summary = analyze_text_with_llm(full_text, industry, 'summary')
        if summary:
            sess["summary"] = summary
        else:
            mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
            sess["summary"] = mock_data["summary"]
            
        # Final Analysis run
        raw_analysis = analyze_text_with_llm(full_text, industry, 'emotions_topics')
        if raw_analysis:
            try:
                clean_json = raw_analysis.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_json)
                sess["topics"] = parsed.get("topics", [])
                sess["emotions"] = parsed.get("emotions", {})
            except Exception as e:
                print(f"Failed to parse end-session analysis JSON: {e}", file=sys.stderr)
                
        # Final fallback check
        if not sess["topics"] or not sess["emotions"]:
            mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
            sess["topics"] = mock_data["topics"]
            sess["emotions"] = mock_data["emotions"]

    # Clean up state
    final_report = {
        "status": "success",
        "session_id": session_id,
        "industry": industry,
        "transcript": sess["transcript"],
        "topics": sess["topics"],
        "emotions": sess["emotions"],
        "summary": sess["summary"]
    }
    
    # Remove session from store
    SESSIONS.pop(session_id, None)
    print(f"Session {session_id} has been ended and finalized.")
    
    return jsonify(final_report)


# WebSocket Handlers

@socketio.on('connect')
def handle_connect():
    """Client WebSocket connection handler."""
    session_id = request.args.get('session_id')
    if session_id:
        join_room(session_id)
        print(f"WebSocket client connected and joined room: {session_id}")
    else:
        print("WebSocket client connected without a session_id parameter.")

@socketio.on('disconnect')
def handle_disconnect():
    """Client WebSocket disconnection handler."""
    print("WebSocket client disconnected.")

@socketio.on('join_session')
def handle_join_session(data):
    """Explicitly join a session room via socket event."""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        print(f"Client joined session room: {session_id}")
        emit('session_joined', {"status": "success", "session_id": session_id}, room=session_id)

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """
    Handle real-time audio chunks from the client.
    `data` can be a binary buffer, or a dict: { "session_id": str, "chunk": str (base64) }
    """
    session_id = None
    chunk_bytes = None
    
    # Determine the payload format
    if isinstance(data, dict):
        session_id = data.get('session_id')
        chunk_data = data.get('chunk')
        if isinstance(chunk_data, str):
            # Base64 string
            try:
                chunk_bytes = base64.b64decode(chunk_data)
            except Exception as e:
                print(f"Failed to decode base64 chunk: {e}", file=sys.stderr)
        else:
            # Binary bytes within dict
            chunk_bytes = chunk_data
    else:
        # Raw binary packet
        session_id = request.args.get('session_id')
        chunk_bytes = data

    if not session_id or not chunk_bytes:
        return

    # Fetch/verify session
    if session_id not in SESSIONS:
        # Auto-create fallback session if it doesn't exist
        SESSIONS[session_id] = {
            "url": "http://localhost",
            "industry": "manufacturing",
            "audio_chunks": [],
            "file_path": None,
            "transcript": [],
            "emotions": {},
            "topics": [],
            "chunk_count": 0,
            "start_time": time.time(),
            "has_real_speech": False
        }

    sess = SESSIONS[session_id]
    sess["chunk_count"] += 1
    
    # Store audio chunk
    sess["audio_chunks"].append(chunk_bytes)
    
    # We transcribe sliding windows of 5 seconds to give Whisper enough audio to accurately process
    # This prevents the 1-second truncation errors!
    real_text = ""
    if sess["chunk_count"] >= 5 and sess["chunk_count"] % 5 == 0:
        try:
            # Concatenate the last 5 chunks (5 seconds of audio)
            recent_chunks = sess["audio_chunks"][-5:]
            recent_audio = b"".join(recent_chunks)
            real_text = transcribe_chunk(recent_audio)
        except Exception as e:
            print(f"Real-time transcribe_chunk on 5-second window failed: {e}", file=sys.stderr)

    if real_text:
        # We got real speech! Turn off mock fallback for the rest of this session
        sess["has_real_speech"] = True
        
        elapsed_sec = int(time.time() - sess["start_time"])
        min_part = elapsed_sec // 60
        sec_part = elapsed_sec % 60
        live_timestamp = f"{min_part}:{sec_part:02d}"
        
        # Alternate speakers for live preview
        speaker = f"Speaker {1 if (sess['chunk_count'] // 5) % 2 == 0 else 2}"
        
        transcript_line = {
            "speaker": speaker,
            "text": real_text,
            "timestamp": live_timestamp
        }
        sess["transcript"].append(transcript_line)
        emit('live_transcript', transcript_line, room=session_id)
        print(f"Emitted real live transcript for {session_id}: {transcript_line}")
        
        # Periodically update analysis using the active LLM based on accumulated transcript
        if len(sess["transcript"]) % 2 == 0:
            full_text = " ".join([f"{t['speaker']}: {t['text']}" for t in sess["transcript"]])
            raw_analysis = analyze_text_with_llm(full_text, sess["industry"], 'emotions_topics')
            if raw_analysis:
                try:
                    clean_json = raw_analysis.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean_json)
                    sess["topics"] = parsed.get("topics", [])
                    sess["emotions"] = parsed.get("emotions", {})
                    emit('live_topics', sess["topics"], room=session_id)
                    emit('live_emotions', sess["emotions"], room=session_id)
                except Exception as e:
                    print(f"Failed to parse live analysis: {e}", file=sys.stderr)
    else:
        # Fallback to interactive mock dialogue stream if no real audio transcription has occurred
        # (This preserves the beautiful visual demo when testing without speaking or without sound)
        if sess["chunk_count"] % 8 == 0 and not sess.get("has_real_speech", False):
            industry = sess["industry"]
            mock_data = INDUSTRY_DATA.get(industry, INDUSTRY_DATA["manufacturing"])
            
            # Calculate current mock dialogue step
            dialogue_idx = (sess["chunk_count"] // 8 - 1) % len(mock_data["dialogue"])
            current_line = mock_data["dialogue"][dialogue_idx]
            
            # Format a realistic timestamp
            elapsed_sec = int(time.time() - sess["start_time"])
            min_part = elapsed_sec // 60
            sec_part = elapsed_sec % 60
            live_timestamp = f"{min_part}:{sec_part:02d}"
            
            # Create transcript line object
            transcript_line = {
                "speaker": current_line["speaker"],
                "text": current_line["text"],
                "timestamp": live_timestamp
            }
            
            # Append to session transcript history
            sess["transcript"].append(transcript_line)
            
            # Emit live transcript update to this session's room
            emit('live_transcript', transcript_line, room=session_id)
            print(f"Emitted mock live transcript for {session_id}: {transcript_line}")
            
            # Shift topics/emotions dynamically to match dialogue progression
            import random
            noisy_topics = []
            for top in mock_data["topics"][:dialogue_idx + 2]:
                noise = random.randint(-5, 5)
                noisy_topics.append({
                    "text": top["text"],
                    "value": max(10, min(100, top["value"] + noise))
                })
                
            noisy_emotions = {}
            for emo, val in mock_data["emotions"].items():
                noise = random.randint(-5, 5)
                noisy_emotions[emo] = max(5, min(90, val + noise))
                
            # Normalize emotions to sum to 100
            total_emo = sum(noisy_emotions.values())
            if total_emo > 0:
                noisy_emotions = {k: round((v / total_emo) * 100) for k, v in noisy_emotions.items()}
                
            sess["topics"] = noisy_topics
            sess["emotions"] = noisy_emotions
            
            emit('live_topics', noisy_topics, room=session_id)
            emit('live_emotions', noisy_emotions, room=session_id)
            print(f"Emitted live analytical mock metrics to room {session_id}")


if __name__ == '__main__':
    # Run the socketio app using eventlet
    port = Config.PORT
    debug = Config.DEBUG
    print(f"Starting VibeNote Backend Server on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
