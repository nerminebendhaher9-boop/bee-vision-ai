"""
wsgi.py — For Gunicorn on Render with Gevent
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.wsgi")

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║       Running on Gunicorn + Gevent                  ║
╚══════════════════════════════════════════════════════╝""")

# Monkey patch for gevent BEFORE any other imports (critical!)
try:
    from gevent import monkey
    monkey.patch_all()
    log.info("✅ Gevent monkey patch applied")
except ImportError:
    log.warning("Gevent not available, WebSocket may not work")

# Now import the application
from app import app, get_tracker, start_broadcast

# WSGI application
application = app

# Lazy initialization — do NOT load model at import time on Render
# The tracker will initialize on first request to /infer or /stats
# This prevents startup crashes if model weights are missing
log.info("WSGI application ready")
log.info("Start command: gunicorn wsgi:application -k gevent -w 1 --bind 0.0.0.0:$PORT")

