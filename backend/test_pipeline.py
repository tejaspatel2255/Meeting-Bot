import os
import sys
import time
import io
import soundfile as sf
import numpy as np

# Add backend directory to system path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from transcriber import transcribe_chunk
from gemini_client import analyze_line, generate_summary
from knowledge_base import scan_for_jargon

def run_test(name, test_func):
    print(f"Running {name}...")
    start_time = time.time()
    try:
        test_func()
        duration = (time.time() - start_time) * 1000
        print(f"  [PASS] {name} succeeded in {duration:.2f} ms\n")
        return True
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        print(f"  [FAIL] {name} failed in {duration:.2f} ms: {e}\n")
        return False

def test_transcribe_chunk():
    # Generate a simple 1-second sine wave at 440Hz
    samplerate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    data = 0.5 * np.sin(2 * np.pi * 440.0 * t)

    # Write wav bytes in-memory
    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, data, samplerate, format='WAV', subtype='PCM_16')
    wav_bytes = wav_buffer.getvalue()

    # Transcribe chunk
    result = transcribe_chunk(wav_bytes)
    print(f"    Transcribe output: '{result}'")
    assert isinstance(result, str), "transcribe_chunk must return a string"

def test_analyze_line():
    text = "We need to calculate the OEE of our assembly line to identify bottlenecks."
    speaker = "Speaker 1"
    industry = "Manufacturing"

    result = analyze_line(text, speaker, industry)
    print(f"    Analyze line output: {result}")
    
    assert isinstance(result, dict), "analyze_line must return a dict"
    for key in ["emotion", "emotion_confidence", "jargon_terms", "insight"]:
        assert key in result, f"Missing key '{key}' in analyze_line output"

def test_scan_for_jargon():
    text = "Let's check the OEE stats and see the Kanban board."
    industry = "Manufacturing"

    matches = scan_for_jargon(text, industry)
    print(f"    Scan for jargon matches: {matches}")
    
    assert isinstance(matches, list), "scan_for_jargon must return a list"
    assert len(matches) > 0, "Should have detected Jargon terms"
    terms = [m["term"].upper() for m in matches]
    assert "OEE" in terms, "Should match term 'OEE'"
    assert "KANBAN" in terms, "Should match term 'Kanban'"

def test_generate_summary():
    transcript = "Speaker 1: Welcome everyone. Speaker 2: We need to increase our OEE immediately. Speaker 1: Agreed, let's assign that to John."
    emotions = [
        {"speaker": "Speaker 1", "emotion": "Positive"},
        {"speaker": "Speaker 2", "emotion": "Neutral"},
        {"speaker": "Speaker 1", "emotion": "Enthusiastic"}
    ]
    industry = "Manufacturing"

    result = generate_summary(transcript, emotions, industry)
    print(f"    Generate summary output: {result}")

    assert isinstance(result, dict), "generate_summary must return a dict"
    for key in ["summary", "key_topics", "decisions", "action_items", "emotional_insights", "overall_sentiment"]:
        assert key in result, f"Missing key '{key}' in generate_summary output"

if __name__ == "__main__":
    print("==================================================")
    print("VibeNote AI Pipeline - Final Integration Testing")
    print("==================================================")
    
    tests = [
        ("Whisper transcribe_chunk test", test_transcribe_chunk),
        ("Gemini analyze_line test", test_analyze_line),
        ("Knowledge Base scan_for_jargon test", test_scan_for_jargon),
        ("Gemini generate_summary test", test_generate_summary)
    ]
    
    all_pass = True
    for name, func in tests:
        success = run_test(name, func)
        if not success:
            all_pass = False
            
    print("==================================================")
    if all_pass:
        print("ALL TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED! [FAILURE]")
        sys.exit(1)
