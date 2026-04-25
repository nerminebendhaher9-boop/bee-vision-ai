"""
wsgi.py - Gunicorn entry point for Render
"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTHONMALLOC'] = 'malloc'

from app import app, socketio  # FIX: must import socketio too

# Gunicorn needs the raw Flask app, but socketio patches it internally.
# With gevent worker + flask-socketio, expose `application = app`
application = app

print("✅ WSGI ready")