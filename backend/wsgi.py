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

from app import app, socketio, get_model

# Pre-load model at startup so first /infer request doesn't time out
try:
    get_model()
    print("✅ Model pre-loaded at startup")
except Exception as e:
    print(f"⚠️  Model pre-load failed: {e}")

application = app