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

# ============================================================
# CRITICAL FIX: Patch engineio BEFORE importing app
# This MUST be here, not in app.py
# ============================================================
import engineio
import engineio.base_server

# Save original init
_original_base_init = engineio.base_server.BaseServer.__init__

def _patched_base_init(self, *args, **kwargs):
    """Fix the logger issue by removing string loggers"""
    # Remove logger if it's a string
    if 'logger' in kwargs and isinstance(kwargs['logger'], str):
        kwargs.pop('logger')
    # Set a proper logger
    if 'logger' not in kwargs:
        kwargs['logger'] = log
    # Call original
    _original_base_init(self, *args, **kwargs)
    # Force set logger if it became a string
    if hasattr(self, 'logger') and isinstance(self.logger, str):
        self.logger = log

# Apply the patch
engineio.base_server.BaseServer.__init__ = _patched_base_init

# Also patch AsyncServer for WebSocket support
if hasattr(engineio, 'async_server') and hasattr(engineio.async_server, 'AsyncServer'):
    _original_async_init = engineio.async_server.AsyncServer.__init__
    def _patched_async_init(self, *args, **kwargs):
        if 'logger' in kwargs and isinstance(kwargs['logger'], str):
            kwargs.pop('logger')
        if 'logger' not in kwargs:
            kwargs['logger'] = log
        _original_async_init(self, *args, **kwargs)
        if hasattr(self, 'logger') and isinstance(self.logger, str):
            self.logger = log
    engineio.async_server.AsyncServer.__init__ = _patched_async_init

log.info("✅ EngineIO logger patched")

# Now import the application (after ALL patches)
from app import app, get_tracker, start_broadcast

# WSGI application
application = app

log.info("WSGI application ready")
log.info(f"Python version: {sys.version}")