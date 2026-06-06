import os
import sys
import uuid
import json
import time
import base64
import tempfile
import threading
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

from config import Config
from transcriber import transcribe_chunk, transcribe_file, assign_speakers
from speaker import diarize
import gemini_client
import knowledge_base

# Create Flask app and configure SocketIO
app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Create upload folder if it doesn't exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# 1. In-memory meeting state dict
meeting_state = {
    "active": False,
    "industry": "manufacturing",
    "transcript": [],
    "emotions": [],
    "topics": [],
    "meeting_id": None
}

# Predefined fallback mock data for visual demo when not speaking or on failure
INDUSTRY_DATA = {
    "manufacturing": {
        "dialogue": [
            {"speaker": "Manager", "text": "Good morning team. Let's review the production delays on Assembly Line 3. The main hydraulic valve is malfunctioning.", "timestamp": "0:05"},
            {"speaker": "Lead Engineer", "text": "Yes, the replacement part is backordered. We are looking at a 48-hour delay unless we source a compatible valve locally.", "timestamp": "0:25"},
            {"speaker": "Manager", "text": "We can't wait 48 hours. Every hour of downtime costs us roughly ten thousand dollars in lost throughput.", "timestamp": "0:45"},
            {"speaker": "Procurement", "text": "I checked Apex Distributors. They have a unit in stock that matches our specs, but it carries a twenty percent markup.", "timestamp": "1:05"},
            {"speaker": "Manager", "text": "Pay the premium and arrange an expedited hot-shot delivery. Also, ensure safety tagout protocols are fully followed before installation.", "timestamp": "1:30"}
        ],
        "topics": ["Line 3 Downtime", "Hydraulic Valve", "Supplier Backlog", "Apex Procurement", "Safety Tagout", "Hourly Loss ($10K)"],
        "emotions": ["Professional", "Urgent", "Concerned", "Relieved", "Neutral"],
        "summary": """### Executive Summary
A critical malfunction of the main hydraulic valve on Assembly Line 3 has halted production. Sourcing the replacement part from the primary supplier would result in a 48-hour delay, costing the plant approximately $240,000. 

### Key Takeaways
- **Downtime Impact:** Every hour of downtime on Line 3 costs $10,000 in lost throughput.
- **Sourcing Strategy:** The primary supplier is backordered, requiring local sourcing.
- **Apex Parts Availability:** Apex Distributors has the part in stock with a 20% markup.
- **Safety Priority:** Maintenance must adhere to Lockout/Tagout (LOTO) safety protocols.

### Action Items
- **[Urgent] Procurement**: Purchase the replacement hydraulic valve from Apex Distributors immediately with expedited shipping. (Deadline: Today)
- **[Safety] Engineering**: Review and update lockout/tagout safety checklists prior to installing the new valve. (Deadline: ASAP)
- **[Operations] Supervisor**: Reallocate line workers to alternative lines to minimize labor downtime during repairs. (Deadline: End of week)
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
        "topics": ["Sector B Foundation", "Zoning Permit", "Soil Density Report", "Steel Framing Crew", "Expedited Inspection", "Project Schedule"],
        "emotions": ["Professional", "Stressed", "Determined", "Focused"],
        "summary": """### Executive Summary
The weekly site meeting addressed a zoning and engineering roadblock on Sector B's foundation. A concrete pour inspector flagged the foundation due to updated soil density readings. The project timeline is at risk, as the steel framing crew arrives next Monday.

### Key Takeaways
- **Inspection Block:** Municipal inspector flagged Sector B concrete pour due to recent soil density changes.
- **Framing Dependency:** Steel framing crew begins next Monday; concrete must be cured.
- **Resolution Plan:** Structural drawings are being revised today to satisfy city codes.
- **Coordination Need:** Direct developer/inspector outreach is required to fast-track approvals.

### Action Items
- **[Urgent] Structural Engineer**: Complete, sign off, and upload the updated structural diagrams to the municipal portal today. (Deadline: 5:00 PM)
- **[Critical] Project Manager**: Contact the building inspector directly to request an expedited review. (Deadline: Thursday)
- **[Logistics] Subcontractor**: Keep concrete trucks on standby for Thursday morning. (Deadline: TBD)
"""
    },
    "financial_services": {
        "dialogue": [
            {"speaker": "Wealth Advisor", "text": "Thanks for joining. Given the Federal Reserve's latest rate hikes, we need to rebalance your asset allocation to mitigate market volatility.", "timestamp": "0:06"},
            {"speaker": "Client", "text": "I've been feeling nervous looking at the market swings. Should we transition some of our equity holdings into safer yields?", "timestamp": "0:24"},
            {"speaker": "Wealth Advisor", "text": "Yes. Short-term Treasury bills are yielding over five percent risk-free. It's a great harbor while equity valuations stabilize.", "timestamp": "0:45"},
            {"speaker": "Client", "text": "That makes sense. Let's do a fifteen percent reallocation from my growth stock index to the high-yield T-bills.", "timestamp": "1:02"},
            {"speaker": "Wealth Advisor", "text": "Sounds like a solid plan. I will draft the authorization documents and send them via DocuSign this afternoon.", "timestamp": "1:22"}
        ],
        "topics": ["Fed Rate Hikes", "Portfolio Rebalancing", "Market Volatility", "Treasury Bills (5%+)", "Asset Allocation", "DocuSign Signature"],
        "emotions": ["Professional", "Calm", "Apprehensive", "Satisfied"],
        "summary": """### Executive Summary
The client advisory call focused on portfolio rebalancing in response to persistent Fed interest rate hikes. To combat market volatility, the advisor suggested relocating capital from volatile equity funds into fixed income. The client agreed to a 15% shift to Short-term US Treasury bills.

### Key Takeaways
- **Rate Environment:** Federal Reserve interest rate hikes make fixed-income instruments highly attractive.
- **Risk Mitigation:** Shifting assets out of growth equities reduces exposure to short-term market swings.
- **T-Bill Yields:** Short-term US Treasuries currently offer >5% risk-free yield.
- **Asset Rebalancing:** Agreed to relocate 15% of the total portfolio into fixed-income Treasuries.

### Action Items
- **[Operational] Wealth Advisor**: Draft the 15% portfolio reallocation forms this morning. (Deadline: ASAP)
- **[Documentation] Client**: Electronically sign the rebalancing authorization documents via DocuSign upon receipt. (Deadline: End of day)
- **[Execution] Advisory Team**: Execute the stock liquidation and Treasury purchase immediately upon signature validation. (Deadline: Next trading day)
"""
    }
}

# Helper: aggregates a list of emotion strings into a percentage dict for the frontend chart
def get_emotions_chart_data(emotions_list):
    if not emotions_list:
        return {"Neutral": 100}
    counts = {}
    for emo in emotions_list:
        counts[emo] = counts.get(emo, 0) + 1
    total = len(emotions_list)
    return {k: round((v / total) * 100) for k, v in counts.items()}

# Helper: compiles structural summary JSON object into standard markdown
def format_summary_markdown(summary_data):
    summary_md = f"### Executive Summary\n{summary_data.get('summary', 'No summary available.')}\n\n### Key Takeaways\n"
    for topic in summary_data.get('key_topics', []):
        summary_md += f"- {topic}\n"
    if not summary_data.get('key_topics'):
        summary_md += "- No key topics recorded.\n"
        
    summary_md += "\n### Decisions\n"
    for dec in summary_data.get('decisions', []):
        summary_md += f"- {dec}\n"
    if not summary_data.get('decisions'):
        summary_md += "- No specific decisions recorded.\n"

    summary_md += "\n### Action Items\n"
    for action in summary_data.get('action_items', []):
        owner = action.get('owner', 'Unassigned')
        task = action.get('task', 'Pending task')
        deadline = action.get('deadline', 'TBD')
        summary_md += f"- **{owner}**: {task} (Deadline: {deadline})\n"
    if not summary_data.get('action_items'):
        summary_md += "- No immediate action items.\n"
        
    return summary_md

# Background Worker Thread for batch audio processing
def process_uploaded_file(file_path, industry, meeting_id):
    try:
        print(f"[Thread] Starting batch audio processing on {file_path}...", flush=True)
        # 1. Runs transcribe_file -> diarize -> assign_speakers in sequence
        whisper_segments = transcribe_file(file_path)
        diarization_intervals = diarize(file_path)
        aligned_segments = assign_speakers(whisper_segments, diarization_intervals)
        
        segments = []
        for seg in aligned_segments:
            start_sec = int(seg.get("start", 0.0))
            min_part = start_sec // 60
            sec_part = start_sec % 60
            timestamp = f"{min_part}:{sec_part:02d}"
            segments.append({
                "speaker": seg.get("speaker", "Unknown"),
                "text": seg.get("text", "").strip(),
                "timestamp": timestamp
            })
            
        # Fallback to mock dialogue if no segments were parsed
        if not segments:
            print("[Thread] No segments transcribed from file. Using industry mock dialogue.", flush=True)
            normalized_ind = industry.lower().replace(" ", "_")
            mock_data = INDUSTRY_DATA.get(normalized_ind, INDUSTRY_DATA["manufacturing"])
            segments = mock_data["dialogue"]

        # 2. For each segment: runs analyze_line + scan_for_jargon
        for idx, seg in enumerate(segments):
            # Guard check if meeting has been reset or stopped in the meantime
            if meeting_state["meeting_id"] != meeting_id or not meeting_state["active"]:
                print(f"[Thread] Session {meeting_id} is no longer active. Aborting file processing.", flush=True)
                return

            text = seg["text"]
            speaker = seg["speaker"]
            timestamp = seg["timestamp"]
            
            # analyze_line internally performs fallback scan_for_jargon matching
            analysis = gemini_client.analyze_line(text, speaker, industry)
            emotion = analysis.get("emotion", "Neutral")
            insight = analysis.get("insight", "")
            jargon_terms = analysis.get("jargon_terms", [])
            
            meeting_state["emotions"].append(emotion)
            
            line_data = {
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp,
                "emotion": emotion,
                "insight": insight,
                "jargon_terms": jargon_terms
            }
            meeting_state["transcript"].append(line_data)
            
            # Emit live updates via SocketIO
            socketio.emit("transcript_line", line_data, room=meeting_id)
            socketio.emit("live_transcript", {"speaker": speaker, "text": text, "timestamp": timestamp}, room=meeting_id)
            
            chart_emotions = get_emotions_chart_data(meeting_state["emotions"])
            socketio.emit("live_emotions", chart_emotions, room=meeting_id)
            
            # 3. Every 10 segments: runs extract_topics
            if (idx + 1) % 10 == 0:
                transcript_so_far = " ".join([f"{l['speaker']}: {l['text']}" for l in meeting_state["transcript"]])
                raw_topics = gemini_client.extract_topics(transcript_so_far)
                meeting_state["topics"] = raw_topics
                
                socketio.emit("topics_update", raw_topics, room=meeting_id)
                formatted_topics = [{"text": t, "value": 70 + (i * 3) % 30} for i, t in enumerate(raw_topics)]
                socketio.emit("live_topics", formatted_topics, room=meeting_id)
                
            time.sleep(0.5)  # slight throttle to create sliding live stream effect
            
        # Final extraction of topics if not extracted
        if not meeting_state["topics"] or len(segments) % 10 != 0:
            transcript_so_far = " ".join([f"{l['speaker']}: {l['text']}" for l in meeting_state["transcript"]])
            raw_topics = gemini_client.extract_topics(transcript_so_far)
            meeting_state["topics"] = raw_topics
            
            socketio.emit("topics_update", raw_topics, room=meeting_id)
            formatted_topics = [{"text": t, "value": 70 + (i * 3) % 30} for i, t in enumerate(raw_topics)]
            socketio.emit("live_topics", formatted_topics, room=meeting_id)

        # Generate full meeting summary
        full_text = " ".join([f"{l['speaker']}: {l['text']}" for l in meeting_state["transcript"]])
        emotions_count = {}
        for emo in meeting_state["emotions"]:
            emotions_count[emo] = emotions_count.get(emo, 0) + 1
        emotions_list = [{"emotion": k, "count": v} for k, v in emotions_count.items()]
        
        summary_res = gemini_client.generate_summary(full_text, emotions_list, industry)
        summary_md = format_summary_markdown(summary_res)
        
        chart_emotions = get_emotions_chart_data(meeting_state["emotions"])
        formatted_topics = [{"text": t, "value": 70 + (i * 3) % 30} for i, t in enumerate(meeting_state["topics"])]
        
        # Emit final report completed event to room
        socketio.emit("final_report", {
            "status": "success",
            "industry": industry,
            "transcript": meeting_state["transcript"],
            "topics": formatted_topics,
            "emotions": chart_emotions,
            "summary": summary_md
        }, room=meeting_id)
        
        print(f"[Thread] Finished processing. Emitted final compiled report for room {meeting_id}.", flush=True)

    except Exception as e:
        print(f"[Thread] Error in background file processing: {e}", file=sys.stderr, flush=True)
    finally:
        # Delete temp file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as df:
                print(f"[Thread] Failed to remove temp file: {df}", file=sys.stderr, flush=True)


# HTTP REST Endpoints

@app.route('/', methods=['GET'])
def health_status():
    """Health check / API status endpoint."""
    return jsonify({
        "status": "online",
        "service": "VibeNote AI Backend Pipeline",
        "engine": "Flask + Flask-SocketIO (eventlet)",
        "models_loaded": {
            "whisper": "Dynamic (lazy-loaded on CPU)",
            "gemini": gemini_client.get_gemini_configured(),
            "groq": gemini_client.get_groq_client() is not None
        }
    })


@app.route('/api/join', methods=['POST'])
def api_join():
    """
    POST /api/join
    Receives {url, industry}
    Detects platform from URL, resets meeting state, and returns session detail.
    """
    data = request.get_json() or {}
    url = data.get('url', 'http://localhost')
    industry = data.get('industry', 'Manufacturing').lower()
    
    # 1. Detect platform from URL
    url_lower = url.lower()
    if "meet.google" in url_lower or "google.com" in url_lower:
        platform = "Google Meet"
    elif "zoom.us" in url_lower or "zoom" in url_lower:
        platform = "Zoom"
    elif "teams.live" in url_lower or "teams.microsoft" in url_lower or "teams" in url_lower:
        platform = "Microsoft Teams"
    else:
        platform = "Web Browser"
        
    # 2. Reset meeting state
    meeting_id = f"sess_{uuid.uuid4().hex[:8]}"
    meeting_state["active"] = True
    meeting_state["industry"] = industry
    meeting_state["transcript"] = []
    meeting_state["emotions"] = []
    meeting_state["topics"] = []
    meeting_state["meeting_id"] = meeting_id
    meeting_state["start_time"] = time.time()
    meeting_state["audio_chunks"] = []
    meeting_state["chunk_count"] = 0
    meeting_state["has_real_speech"] = False
    
    print(f"Session Joined: {meeting_id} | Platform: {platform} | Industry: {industry}", flush=True)
    
    # Returns {status: "ready", meeting_id, platform} (with backward compatibility key session_id)
    return jsonify({
        "status": "ready",
        "meeting_id": meeting_id,
        "platform": platform,
        "session_id": meeting_id  # for frontend app.js
    })


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """
    POST /api/upload
    Receives multipart audio file
    Saves to /tmp/, runs pipeline in background thread, returns processing status.
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    industry = request.form.get('industry', 'Manufacturing').lower()
    if industry not in ["manufacturing", "construction", "financial services"]:
        industry = "manufacturing"

    # Save to temp directory
    temp_dir = tempfile.gettempdir()
    file_id = uuid.uuid4().hex[:8]
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)
    
    print(f"File uploaded to {file_path}. Resetting meeting state to background processing...", flush=True)
    
    # Reset and initialize meeting state
    meeting_id = f"sess_{uuid.uuid4().hex[:8]}"
    meeting_state["active"] = True
    meeting_state["industry"] = industry
    meeting_state["transcript"] = []
    meeting_state["emotions"] = []
    meeting_state["topics"] = []
    meeting_state["meeting_id"] = meeting_id
    meeting_state["start_time"] = time.time()
    meeting_state["audio_chunks"] = []
    meeting_state["chunk_count"] = 0
    meeting_state["has_real_speech"] = False
    
    # Threading for upload processing
    thread = threading.Thread(target=process_uploaded_file, args=(file_path, industry, meeting_id))
    thread.daemon = True
    thread.start()
    
    # Returns {status: "processing"} immediately (with helpers for frontend room routing)
    return jsonify({
        "status": "processing",
        "meeting_id": meeting_id,
        "session_id": meeting_id  # for frontend room mapping
    })


@app.route('/api/end', methods=['POST'])
def api_end():
    """
    POST /api/end
    Sets active=False, builds full transcript, runs generate_summary, returns compiled report.
    """
    data = request.get_json() or {}
    session_id = data.get('session_id') or data.get('meeting_id')
    
    if not session_id or session_id != meeting_state["meeting_id"]:
        return jsonify({"status": "error", "message": "Invalid or inactive session ID"}), 400
        
    # Set active=False
    meeting_state["active"] = False
    industry = meeting_state["industry"]
    
    # If transcript is completely empty, default to mock data so the dashboard doesn't display blank
    if not meeting_state["transcript"]:
        normalized_ind = industry.lower().replace(" ", "_")
        mock_data = INDUSTRY_DATA.get(normalized_ind, INDUSTRY_DATA["manufacturing"])
        
        # Populate state from mock data
        meeting_state["transcript"] = mock_data["dialogue"]
        meeting_state["topics"] = mock_data["topics"]
        meeting_state["emotions"] = mock_data["emotions"]
        summary_md = mock_data["summary"]
    else:
        # Build full transcript string
        full_text = " ".join([f"{item['speaker']}: {item['text']}" for item in meeting_state["transcript"]])
        
        # Aggregate emotions to a list
        emotions_count = {}
        for emo in meeting_state["emotions"]:
            emotions_count[emo] = emotions_count.get(emo, 0) + 1
        emotions_list = [{"emotion": k, "count": v} for k, v in emotions_count.items()]
        
        # Run generate_summary
        summary_res = gemini_client.generate_summary(full_text, emotions_list, industry)
        summary_md = format_summary_markdown(summary_res)
        
        # Run extract_topics if topics list is empty
        if not meeting_state["topics"]:
            raw_topics = gemini_client.extract_topics(full_text)
            meeting_state["topics"] = raw_topics

    chart_emotions = get_emotions_chart_data(meeting_state["emotions"])
    formatted_topics = [{"text": t, "value": 70 + (i * 3) % 30} for i, t in enumerate(meeting_state["topics"])]
    
    final_report = {
        "status": "success",
        "session_id": session_id,
        "meeting_id": session_id,
        "industry": industry,
        "transcript": meeting_state["transcript"],
        "topics": formatted_topics,
        "emotions": chart_emotions,
        "summary": summary_md
    }
    
    print(f"Session {session_id} finalized and ended.", flush=True)
    return jsonify(final_report)


@app.route('/api/state', methods=['GET'])
def api_state():
    """
    GET /api/state
    Returns the current meeting_state (useful for dashboard reconnection)
    """
    return jsonify(meeting_state)


# WebSockets Handlers

@socketio.on('connect')
def handle_connect():
    print("WebSocket client connected.", flush=True)


@socketio.on('disconnect')
def handle_disconnect():
    print("WebSocket client disconnected.", flush=True)


@socketio.on('join_session')
def handle_join_session(data):
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        print(f"Client joined Socket room: {session_id}", flush=True)
        emit('session_joined', {"status": "success", "session_id": session_id}, room=session_id)


@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """
    WebSocket event "audio_chunk"
    Receives {audio: base64, speaker: str} (or compatible {session_id, chunk})
    Decodes audio, runs transcribe_chunk, analyze_line, scan_for_jargon, extract_topics, and emits updates.
    """
    if not isinstance(data, dict):
        return
        
    session_id = data.get('session_id') or meeting_state["meeting_id"]
    audio_base64 = data.get('audio') or data.get('chunk')
    speaker = data.get('speaker') or "Speaker"
    
    if not session_id or not audio_base64:
        return
        
    # Decodes audio
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as de:
        print(f"Failed to decode base64 chunk: {de}", file=sys.stderr, flush=True)
        return
        
    # Store chunk in state buffer
    if "audio_chunks" not in meeting_state:
        meeting_state["audio_chunks"] = []
    meeting_state["audio_chunks"].append(audio_bytes)
    
    if "chunk_count" not in meeting_state:
        meeting_state["chunk_count"] = 0
    meeting_state["chunk_count"] += 1
    
    real_text = ""
    # Transcribe sliding windows of 5 seconds to provide accurate context to Whisper
    if meeting_state["chunk_count"] >= 5 and meeting_state["chunk_count"] % 5 == 0:
        try:
            recent_audio = b"".join(meeting_state["audio_chunks"][-5:])
            real_text = transcribe_chunk(recent_audio)
        except Exception as te:
            print(f"Real-time transcribe_chunk failed: {te}", file=sys.stderr, flush=True)
            
    if real_text:
        meeting_state["has_real_speech"] = True
        elapsed_sec = int(time.time() - meeting_state.get("start_time", time.time()))
        min_part = elapsed_sec // 60
        sec_part = elapsed_sec % 60
        timestamp = f"{min_part}:{sec_part:02d}"
        
        # 1. Run analyze_line + scan_for_jargon
        analysis = gemini_client.analyze_line(real_text, speaker, meeting_state["industry"])
        emotion = analysis.get("emotion", "Neutral")
        insight = analysis.get("insight", "")
        jargon_terms = analysis.get("jargon_terms", [])
        
        # Update meeting state
        meeting_state["emotions"].append(emotion)
        line_data = {
            "speaker": speaker,
            "text": real_text,
            "timestamp": timestamp,
            "emotion": emotion,
            "insight": insight,
            "jargon_terms": jargon_terms,
            "real_speech": True
        }
        meeting_state["transcript"].append(line_data)
        
        # 2. Emits "transcript_line" event with full enriched line
        emit("transcript_line", line_data, room=session_id)
        # Compatible event for frontend
        emit("live_transcript", {"speaker": speaker, "text": real_text, "timestamp": timestamp}, room=session_id)
        
        chart_emotions = get_emotions_chart_data(meeting_state["emotions"])
        emit("live_emotions", chart_emotions, room=session_id)
        
        # 3. Every 10 lines runs extract_topics
        if len(meeting_state["transcript"]) % 10 == 0:
            transcript_so_far = " ".join([f"{l['speaker']}: {l['text']}" for l in meeting_state["transcript"]])
            raw_topics = gemini_client.extract_topics(transcript_so_far)
            meeting_state["topics"] = raw_topics
            
            # Emits "topics_update" and "live_topics"
            emit("topics_update", raw_topics, room=session_id)
            formatted_topics = [{"text": t, "value": 70 + (i * 3) % 30} for i, t in enumerate(raw_topics)]
            emit("live_topics", formatted_topics, room=session_id)
            
    else:
        # Fallback to visual mock demo stream if no speech is detected (keeps UI alive and interactive)
        if meeting_state["chunk_count"] % 8 == 0 and not meeting_state.get("has_real_speech", False):
            normalized_ind = meeting_state["industry"].lower().replace(" ", "_")
            mock_data = INDUSTRY_DATA.get(normalized_ind, INDUSTRY_DATA["manufacturing"])
            
            # Dialogue rotation index
            dialogue_idx = (meeting_state["chunk_count"] // 8 - 1) % len(mock_data["dialogue"])
            current_line = mock_data["dialogue"][dialogue_idx]
            
            elapsed_sec = int(time.time() - meeting_state["start_time"])
            min_part = elapsed_sec // 60
            sec_part = elapsed_sec % 60
            timestamp = f"{min_part}:{sec_part:02d}"
            
            # Run local jargon scanner to showcase knowledge base capability
            jargon_matches = knowledge_base.scan_for_jargon(current_line["text"], meeting_state["industry"])
            formatted_jargon = [{"term": j["term"], "plain_english": f"{j['full_form']}: {j['plain_english']}"} for j in jargon_matches]
            
            # Mock analyze line
            emotion = mock_data["emotions"][dialogue_idx % len(mock_data["emotions"])]
            meeting_state["emotions"].append(emotion)
            
            line_data = {
                "speaker": current_line["speaker"],
                "text": current_line["text"],
                "timestamp": timestamp,
                "emotion": emotion,
                "insight": f"Important discussion regarding {meeting_state['industry']} operations.",
                "jargon_terms": formatted_jargon,
                "real_speech": False
            }
            meeting_state["transcript"].append(line_data)
            
            emit("transcript_line", line_data, room=session_id)
            emit("live_transcript", {"speaker": current_line["speaker"], "text": current_line["text"], "timestamp": timestamp}, room=session_id)
            
            chart_emotions = get_emotions_chart_data(meeting_state["emotions"])
            emit("live_emotions", chart_emotions, room=session_id)
            
            # Periodic mock topic updates
            import random
            noisy_topics = []
            for top in mock_data["topics"][:dialogue_idx + 2]:
                noise = random.randint(-5, 5)
                noisy_topics.append({
                    "text": top,
                    "value": max(10, min(100, 75 + noise))
                })
            
            meeting_state["topics"] = [nt["text"] for nt in noisy_topics]
            emit("topics_update", meeting_state["topics"], room=session_id)
            emit("live_topics", noisy_topics, room=session_id)


if __name__ == '__main__':
    port = Config.PORT
    debug = Config.DEBUG
    print(f"Starting VibeNote Backend Server on port {port}...", flush=True)
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
