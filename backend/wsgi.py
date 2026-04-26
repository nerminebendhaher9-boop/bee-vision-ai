from gevent import monkey
monkey.patch_all()

import sys
import os
from pathlib import Path

# Add backend directory to PYTHONPATH
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Import the Flask app and SocketIO after monkey patching
from app import app, socketio, log

# The model is already being loaded in app.py via background thread
log.info("✅ Starting Gunicorn server - model will load in background")

# Application for Gunicorn
application = app

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))