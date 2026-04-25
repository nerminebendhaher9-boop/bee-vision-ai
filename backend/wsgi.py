# MUST be first — before everything
from gevent import monkey
monkey.patch_all()

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTHONMALLOC'] = 'malloc'

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Starting on Render             ║
╚══════════════════════════════════════════════════════╝""")

from app import app, socketio

# Model is lazy-loaded on first /infer request to avoid OOM/boot timeout
# on Render free tier (512MB RAM). Pre-loading at import time often kills
# the worker before gunicorn finishes booting.

application = app
