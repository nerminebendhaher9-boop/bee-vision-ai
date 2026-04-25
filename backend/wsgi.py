from gevent import monkey
monkey.patch_all()

import sys
import os
from pathlib import Path

# Ajoutez le répertoire parent au PYTHONPATH pour que app.py soit trouvable
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Importez l'application Flask et SocketIO après le monkey patching
from app import app, socketio, _load_model_background, log

# Chargez le modèle de manière synchrone avant que Gunicorn ne commence à servir
log.info("⏳ Loading YOLO model at startup (from wsgi.py)...")
try:
    _load_model_background()
    log.info("✅ Model ready (from wsgi.py)")
except Exception as e:
    log.error(f"❌ Model load failed (from wsgi.py): {e}")

# L'application pour Gunicorn
application = app