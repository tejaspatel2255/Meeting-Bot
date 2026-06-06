import subprocess
import os
import sys
import time

xvfb_process = None

def is_xvfb_running() -> bool:
    """Checks if Xvfb is running via subprocess state or existing display socket."""
    global xvfb_process
    if xvfb_process is not None and xvfb_process.poll() is None:
        return True
    # Fallback to checking socket existence on display :99
    if os.path.exists("/tmp/.X11-unix/X99"):
        return True
    return False

def start_xvfb():
    """Starts the virtual framebuffer server on DISPLAY=:99 if not already running."""
    global xvfb_process
    if is_xvfb_running():
        print("Xvfb is already running on Display :99", flush=True)
        os.environ["DISPLAY"] = ":99"
        return
        
    print("Starting virtual display server (Xvfb :99)...", flush=True)
    try:
        # Launch headless virtual display buffer
        xvfb_process = subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1.5)  # Wait for display initialization
        os.environ["DISPLAY"] = ":99"
        print("Xvfb display server initialized successfully.", flush=True)
    except Exception as e:
        print(f"Failed to start Xvfb virtual frame buffer: {e}", file=sys.stderr, flush=True)

def stop_xvfb():
    """Stops the active Xvfb display process."""
    global xvfb_process
    if xvfb_process is not None:
        print("Stopping Xvfb display server...", flush=True)
        try:
            xvfb_process.terminate()
            xvfb_process.wait(timeout=5)
        except Exception:
            xvfb_process.kill()
        xvfb_process = None
        print("Xvfb display server stopped.", flush=True)
