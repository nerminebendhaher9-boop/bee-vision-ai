from gevent import monkey
monkey.patch_all()

import sys
import os
from pathlib import Path

# Add backend directory to PYTHONPATH
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Import the Flask app after monkey patching
from app import app, log

log.info("✅ Starting Gunicorn server with gevent worker")

# Application for Gunicorn
application = app

if __name__ == "__main__":
    from app import socketio
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))