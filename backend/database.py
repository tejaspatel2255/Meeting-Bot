import sqlite3, json, threading
from datetime import datetime
import os

# Create in backend folder
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vibenote.db")

class Database:
    def __init__(self):
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables if they don't exist"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS meetings (
                    meeting_id TEXT PRIMARY KEY,
                    platform TEXT,
                    industry TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS transcript_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT,
                    speaker TEXT,
                    text TEXT,
                    emotion TEXT,
                    emotion_confidence REAL,
                    jargon_terms TEXT,
                    insight TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT UNIQUE,
                    summary_text TEXT,
                    key_topics TEXT,
                    decisions TEXT,
                    action_items TEXT,
                    emotional_insights TEXT,
                    overall_sentiment TEXT,
                    created_at TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
                );
            """)

    def save_meeting(self, meeting_id, platform, industry, email=None):
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO meetings 
                    (meeting_id, platform, industry, email, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (meeting_id, platform, industry, email,
                      datetime.utcnow().isoformat()))

    def save_transcript_line(self, meeting_id: str, line: dict):
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO transcript_lines
                    (meeting_id, speaker, text, emotion, emotion_confidence,
                     jargon_terms, insight, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meeting_id,
                    line.get("speaker"),
                    line.get("text"),
                    line.get("emotion"),
                    line.get("emotion_confidence"),
                    json.dumps(line.get("jargon_terms", [])),
                    line.get("insight"),
                    datetime.utcnow().isoformat()
                ))

    def save_summary(self, meeting_id: str, summary: dict):
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO summaries
                    (meeting_id, summary_text, key_topics, decisions,
                     action_items, emotional_insights, overall_sentiment, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meeting_id,
                    summary.get("summary"),
                    json.dumps(summary.get("key_topics", [])),
                    json.dumps(summary.get("decisions", [])),
                    json.dumps(summary.get("action_items", [])),
                    json.dumps(summary.get("emotional_insights", [])),
                    summary.get("overall_sentiment"),
                    datetime.utcnow().isoformat()
                ))
                conn.execute("""
                    UPDATE meetings SET status='ended', ended_at=?
                    WHERE meeting_id=?
                """, (datetime.utcnow().isoformat(), meeting_id))

    def get_meeting(self, meeting_id: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM meetings WHERE meeting_id=?",
                (meeting_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_transcript(self, meeting_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM transcript_lines 
                WHERE meeting_id=? ORDER BY id ASC
            """, (meeting_id,)).fetchall()
            lines = []
            for row in rows:
                d = dict(row)
                d["jargon_terms"] = json.loads(d["jargon_terms"] or "[]")
                lines.append(d)
            return lines

    def get_summary(self, meeting_id: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM summaries WHERE meeting_id=?",
                (meeting_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            for field in ["key_topics","decisions","action_items","emotional_insights"]:
                d[field] = json.loads(d[field] or "[]")
            return d

    def get_all_meetings(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT m.*, s.overall_sentiment 
                FROM meetings m
                LEFT JOIN summaries s ON m.meeting_id = s.meeting_id
                ORDER BY m.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

# Single global instance
db = Database()
