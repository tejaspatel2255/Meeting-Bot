import threading
import os
from bot.xvfb_manager import start_xvfb, is_xvfb_running
from bot.meet_bot import GoogleMeetBot
from bot.zoom_bot import ZoomBot
from bot.teams_bot import TeamsBot

# Active bots dictionary: keyed by meeting_id -> bot instance
active_bots = {}

def launch_bot(url: str, meeting_id: str, industry: str, socketio_instance) -> str:
    """
    Detects meeting platform from the URL, initializes Xvfb if on Linux 
    and missing DISPLAY, and starts the correct bot in a background daemon thread.
    """
    global active_bots
    
    url_lower = url.lower()
    
    # 1. Determine platform and select bot class
    if "meet.google" in url_lower or "google.com" in url_lower:
        bot_class = GoogleMeetBot
        platform = "Google Meet"
    elif "zoom.us" in url_lower or "zoom" in url_lower:
        bot_class = ZoomBot
        platform = "Zoom"
    elif "teams.microsoft" in url_lower or "teams.live" in url_lower or "teams" in url_lower:
        bot_class = TeamsBot
        platform = "Microsoft Teams"
    else:
        print(f"[Bot Launcher] Platform not supported for URL: {url}. Fallback to GoogleMeetBot.", flush=True)
        bot_class = GoogleMeetBot
        platform = "Google Meet"
        
    print(f"[Bot Launcher] Launching bot for {platform} | URL: {url} | Meeting ID: {meeting_id}", flush=True)
    
    # 2. Check and start Xvfb if running in headless Linux environment
    # On Windows, DISPLAY is not a standard var, so we don't start Xvfb.
    if os.name != 'nt' and "DISPLAY" not in os.environ:
        start_xvfb()
        
    # 3. Instantiate bot
    bot = bot_class(url, meeting_id, industry, socketio_instance)
    active_bots[meeting_id] = bot
    
    # 4. Start in a background daemon thread so it does not block Flask execution
    thread = threading.Thread(target=bot.start)
    thread.daemon = True
    thread.start()
    
    return platform

def stop_bot(meeting_id: str):
    """Gracefully terminates a bot session and cleans up references."""
    global active_bots
    if meeting_id in active_bots:
        print(f"[Bot Launcher] Stopping bot for meeting: {meeting_id}", flush=True)
        bot = active_bots[meeting_id]
        bot.stop()
        del active_bots[meeting_id]
    else:
        print(f"[Bot Launcher] No active bot found to stop for meeting: {meeting_id}", flush=True)

def get_bot_status_info(meeting_id: str) -> dict:
    """Returns status data for a given bot session."""
    global active_bots
    if meeting_id in active_bots:
        bot = active_bots[meeting_id]
        # Determine platform name
        if isinstance(bot, GoogleMeetBot):
            platform = "Google Meet"
        elif isinstance(bot, ZoomBot):
            platform = "Zoom"
        elif isinstance(bot, TeamsBot):
            platform = "Microsoft Teams"
        else:
            platform = "Unknown"
            
        return {
            "status": bot.status,
            "platform": platform,
            "meeting_id": meeting_id,
            "logs": bot.logs,
            "error": bot.error_msg
        }
    return {
        "status": "stopped",
        "platform": "None",
        "meeting_id": meeting_id,
        "logs": ["No active bot session"],
        "error": None
    }
