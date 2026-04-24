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

# FIX ENGINEIO LOGGER ISSUE FOR PYTHON 3.14
import engineio
import engineio.base_server

# Monkey patch the BaseServer to fix logger issue
_original_init = engineio.base_server.BaseServer.__init__

def _patched_init(self, *args, **kwargs):
    # Remove logger if it's a string
    if 'logger' in kwargs and isinstance(kwargs['logger'], str):
        kwargs.pop('logger')
    # Set our logger
    kwargs['logger'] = log
    _original_init(self, *args, **kwargs)
    # Force set logger if it became a string
    if hasattr(self, 'logger') and isinstance(self.logger, str):
        self.logger = log

engineio.base_server.BaseServer.__init__ = _patched_init

# Also patch AsyncServer if it exists
if hasattr(engineio, 'async_server') and hasattr(engineio.async_server, 'AsyncServer'):
    _original_async_init = engineio.async_server.AsyncServer.__init__
    def _patched_async_init(self, *args, **kwargs):
        if 'logger' in kwargs and isinstance(kwargs['logger'], str):
            kwargs.pop('logger')
        kwargs['logger'] = log
        _original_async_init(self, *args, **kwargs)
        if hasattr(self, 'logger') and isinstance(self.logger, str):
            self.logger = log
    engineio.async_server.AsyncServer.__init__ = _patched_async_init

log.info("✅ EngineIO logger patched for Python 3.14 compatibility")

# Now import the application
from app import app, get_tracker, start_broadcast

# WSGI application
application = app

log.info("WSGI application ready")