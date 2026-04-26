from gevent import monkey
monkey.patch_all()

import sys
import os
from pathlib import Path

# Add backend directory to PYTHONPATH
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Import AFTER monkey patching
from app import app, log

log.info("✅ WSGI initialized (gevent)")

# Gunicorn entry point
application = app