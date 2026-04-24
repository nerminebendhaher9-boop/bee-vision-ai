"""
wsgi.py — For Gunicorn on Render with Gevent
"""
from __future__ import annotations

import sys
import os
import logging
from pathlib import Path

# Force Python to use unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# CRITICAL: Monkey patch at the VERY TOP
from gevent import monkey
monkey.patch_all()

# Add paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Setup logging
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

# Import app
from app import app

# WSGI application
application = app

log.info("WSGI application ready")