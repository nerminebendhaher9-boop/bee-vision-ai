"""
wsgi.py - Entry point for Gunicorn on Render with Python 3.12
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Memory optimization for Python 3.12
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTHONMALLOC'] = 'malloc'  # Better memory management for 3.12

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Python 3.12 on Render          ║
╚══════════════════════════════════════════════════════╝""")

from app import app

# For Gunicorn
application = app

print("✅ WSGI application ready for Python 3.12")