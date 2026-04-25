"""
wsgi.py - Entry point for Gunicorn on Render
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Set memory optimization
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  WSGI Entry Point               ║
║          Running on Render with Gunicorn            ║
╚══════════════════════════════════════════════════════╝""")

from app import app, socketio

# For Gunicorn
application = app

print("✅ WSGI application ready")