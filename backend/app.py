"""
backend/app.py — BEE AI PRO Main Flask App
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bee.app")

from flask import Flask, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║            Ready for Render Deployment              ║
╚══════════════════════════════════════════════════════╝""")

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"

CORS(app, origins=["*"])

import os
_is_render = os.environ.get('RENDER', False)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='gevent',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

log.info(f"SocketIO initialized with async_mode: {socketio.async_mode}")

@app.route('/health')
def health():
    return jsonify({"status": "ok", "socketio": "ready"})

@app.route('/test')
def test():
    return jsonify({"status": "ok", "message": "Bee AI backend running"})

@socketio.on('connect')
def handle_connect():
    log.info("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    log.info("Client disconnected")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)
else:
    log.info("App created for Gunicorn")