import os
import sys
import json
from config import Config
from groq import Groq
import google.generativeai as genai

# Cache variables for client configurations
_groq_client = None
_gemini_configured = False

def get_groq_client():
    """Initializes and returns the Groq client if the API key is configured."""
    global _groq_client
    if _groq_client is None:
        api_key = Config.GROQ_API_KEY
        if api_key:
            try:
                _groq_client = Groq(api_key=api_key)
            except Exception as e:
                print(f"Error initializing Groq client: {e}", file=sys.stderr, flush=True)
    return _groq_client

def get_gemini_configured():
    """Configures Gemini with the API key and returns True if successful."""
    global _gemini_configured
    if not _gemini_configured:
        api_key = Config.GEMINI_API_KEY
        if api_key:
            try:
                genai.configure(api_key=api_key)
                _gemini_configured = True
            except Exception as e:
                print(f"Error configuring Gemini: {e}", file=sys.stderr, flush=True)
    return _gemini_configured


def clean_and_parse_json(text: str):
    """
    Robust JSON parser that handles potential raw JSON strings, markdown code blocks,
    or leading/trailing conversational text returned by LLMs.
    """
    text = text.strip()
    
    # Strip markdown code blocks if the model wrapped its response in them
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part_clean = part.strip()
            if part_clean.startswith("json"):
                part_clean = part_clean[4:].strip()
            if part_clean:
                try:
                    return json.loads(part_clean)
                except json.JSONDecodeError:
                    continue
                    
    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: find the first and last JSON-like markers
        try:
            start_idx = min([i for i in [text.find('{'), text.find('[')] if i != -1])
            end_idx = max([i for i in [text.rfind('}'), text.rfind(']')] if i != -1])
            if start_idx != -1 and end_idx != -1:
                return json.loads(text[start_idx:end_idx+1])
        except Exception:
            pass
            
    raise ValueError(f"Could not parse valid JSON from LLM response: {text}")


def call_llm(prompt: str) -> str:
    """
    Core caller that routes prompts to Groq (primary) and falls back to Gemini (secondary).
    Logs which client was successfully invoked.
    """
    # 1. Try Groq (Primary AI)
    groq_cli = get_groq_client()
    if groq_cli:
        try:
            print("[LLM Call] Invoking Groq (llama3-8b-8192) as primary model...", flush=True)
            chat_completion = groq_cli.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
                temperature=0.1
            )
            if chat_completion.choices and chat_completion.choices[0].message.content:
                response_text = chat_completion.choices[0].message.content.strip()
                print("[LLM Call] Success: Groq (llama3-8b-8192) processed the request.", flush=True)
                return response_text
        except Exception as e:
            print(f"[LLM Call] Groq primary call failed: {e}. Attempting fallback to Gemini...", file=sys.stderr, flush=True)

    # 2. Try Gemini (Fallback AI)
    if get_gemini_configured():
        try:
            print("[LLM Call] Invoking Gemini (gemini-2.5-flash) as fallback model...", flush=True)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            if response and response.text:
                response_text = response.text.strip()
                print("[LLM Call] Success: Gemini (gemini-2.5-flash) processed the request.", flush=True)
                return response_text
        except Exception as e:
            print(f"[LLM Call] Gemini fallback call failed: {e}.", file=sys.stderr, flush=True)

    raise RuntimeError("Both Groq and Gemini models failed or were not configured.")


def analyze_line(text: str, speaker: str, industry: str) -> dict:
    """
    Analyzes a single transcript line for emotion, jargon, and insights.
    Returns structured JSON.
    """
    prompt = f"""
    Analyze the following single line spoken by '{speaker}' in a meeting related to the '{industry}' industry.
    
    Spoken text: "{text}"
    
    You must return ONLY a valid JSON object matching this structure exactly. Do not wrap in markdown tags or include explanations:
    {{
      "emotion": "Positive|Negative|Neutral|Confused|Hesitant|Enthusiastic",
      "emotion_confidence": 0.85,
      "jargon_terms": [
        {{"term": "jargon word", "plain_english": "simple explanation"}}
      ],
      "insight": "a single sentence key insight or empty string"
    }}
    """
    default_response = {
        "emotion": "Neutral",
        "emotion_confidence": 1.0,
        "jargon_terms": [],
        "insight": ""
    }
    
    try:
        response_text = call_llm(prompt)
        parsed = clean_and_parse_json(response_text)
        
        # Ensure all required keys exist
        for key in ["emotion", "emotion_confidence", "jargon_terms", "insight"]:
            if key not in parsed:
                parsed[key] = default_response[key]
        return parsed
    except Exception as e:
        print(f"Error in analyze_line: {e}. Returning safe default.", file=sys.stderr, flush=True)
        return default_response


def extract_topics(transcript_so_far: str) -> list[str]:
    """
    Extracts 5-8 main topic strings discussed in the transcript so far.
    Returns list of strings.
    """
    prompt = f"""
    Identify the main topics discussed in the following conversation transcript.
    
    Transcript:
    "{transcript_so_far}"
    
    You must return ONLY a JSON array containing 5 to 8 topic strings. Do not wrap in markdown tags or include explanations.
    Example output format:
    ["Topic A", "Topic B", "Topic C"]
    """
    default_response = []
    
    try:
        response_text = call_llm(prompt)
        parsed = clean_and_parse_json(response_text)
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
        elif isinstance(parsed, dict) and "topics" in parsed:
            return [str(t) for t in parsed["topics"]]
        return default_response
    except Exception as e:
        print(f"Error in extract_topics: {e}. Returning safe default.", file=sys.stderr, flush=True)
        return default_response


def generate_summary(full_transcript: str, emotions: list, industry: str) -> dict:
    """
    Generates a full meeting summary report with key topics, decisions, action items,
    and emotional metrics. Returns structured JSON.
    """
    emotions_str = json.dumps(emotions)
    prompt = f"""
    Provide an executive summary and structured analysis of the following meeting transcript from the '{industry}' industry.
    The emotional data detected in the session was: {emotions_str}
    
    Transcript:
    "{full_transcript}"
    
    You must return ONLY a valid JSON object matching this structure exactly. Do not wrap in markdown tags or include explanations:
    {{
      "summary": "a 2-3 sentence overview of the meeting",
      "key_topics": ["topic A", "topic B"],
      "decisions": ["decision 1", "decision 2"],
      "action_items": [
        {{"owner": "John Doe", "task": "do task X", "deadline": "ASAP/End of week"}}
      ],
      "emotional_insights": ["insight about session tone"],
      "overall_sentiment": "Positive|Mixed|Negative"
    }}
    """
    default_response = {
        "summary": "No summary available.",
        "key_topics": [],
        "decisions": [],
        "action_items": [],
        "emotional_insights": [],
        "overall_sentiment": "Mixed"
    }
    
    try:
        response_text = call_llm(prompt)
        parsed = clean_and_parse_json(response_text)
        
        # Ensure all required keys exist
        for key in ["summary", "key_topics", "decisions", "action_items", "emotional_insights", "overall_sentiment"]:
            if key not in parsed:
                parsed[key] = default_response[key]
        return parsed
    except Exception as e:
        print(f"Error in generate_summary: {e}. Returning safe default.", file=sys.stderr, flush=True)
        return default_response
