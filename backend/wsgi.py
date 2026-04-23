"""
wsgi.py — For Gunicorn on Render with Eventlet
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.wsgi")

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║       Running on Gunicorn + Eventlet                ║
╚══════════════════════════════════════════════════════╝""")

# Import application
from app import app, socketio, get_tracker, start_broadcast

# Monkey patch for eventlet (important!)
try:
    import eventlet
    eventlet.monkey_patch()
    log.info("✅ Eventlet monkey patch applied")
except ImportError:
    log.warning("Eventlet not available, WebSocket may not work")

# Initialize tracker
log.info("Initializing tracker...")
try:
    tracker = get_tracker()
    if tracker:
        log.info("✅ Tracker initialized")
except Exception as e:
    log.error(f"Tracker init error: {e}")
    log.info("Tracker will initialize on first request")

# Start broadcast
try:
    start_broadcast()
    log.info("✅ Broadcast started")
except Exception as e:
    log.warning(f"Broadcast not started: {e}")

# WSGI application
application = app

log.info("WSGI application ready for Gunicorn with Eventlet")
log.info("Start command: gunicorn wsgi:application -k eventlet -w 1 --bind 0.0.0.0:$PORT")