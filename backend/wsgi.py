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

# ============================================================
# CRITICAL: Patch engineio BEFORE any other imports
# ============================================================
import engineio
import engineio.base_server

_original_base_init = engineio.base_server.BaseServer.__init__

def _patched_base_init(self, *args, **kwargs):
    if 'logger' in kwargs and isinstance(kwargs['logger'], str):
        kwargs.pop('logger')
    if 'logger' not in kwargs:
        kwargs['logger'] = logging.getLogger('engineio')
    _original_base_init(self, *args, **kwargs)
    if hasattr(self, 'logger') and isinstance(self.logger, str):
        self.logger = logging.getLogger('engineio')

engineio.base_server.BaseServer.__init__ = _patched_base_init

# ============================================================
# Normal imports
# ============================================================

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
log.info("✅ EngineIO logger patched")

# Import app
from app import app

# WSGI application
application = app

log.info("WSGI application ready")