"""
wsgi.py — For Gunicorn on Render with Gevent
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# CRITICAL: Monkey patch at the VERY TOP before ANY other imports
from gevent import monkey
monkey.patch_all()

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

log.info("✅ Gevent monkey patch applied")

# Now import the application (after monkey patch)
from app import app, get_tracker, start_broadcast

# WSGI application
application = app

# Disable logger string issue by configuring engineio properly
import engineio
engineio.logger = log

log.info("WSGI application ready")