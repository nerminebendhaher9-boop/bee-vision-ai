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

from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║            Ready for Render Deployment              ║
╚══════════════════════════════════════════════════════╝""")

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"

# ============================================================
# CORS - SINGLE CONFIGURATION ONLY
# ============================================================
CORS(app, 
     origins=["https://bee-vision-ai.onrender.com", "http://localhost:5173", "http://localhost:3000"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"],
     supports_credentials=True)

# ── SocketIO configuration ──────────────────────────────────────
import os
_is_render = os.environ.get('RENDER', False)

socketio = SocketIO(
    app,
    cors_allowed_origins="https://bee-vision-ai.onrender.com",
    async_mode='gevent',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

log.info(f"SocketIO initialized with async_mode: {socketio.async_mode}")

# ============================================================
# ROUTES
# ============================================================
@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    return jsonify({"status": "ok", "socketio": "ready"})

@app.route('/test', methods=['GET', 'OPTIONS'])
def test():
    return jsonify({
        'status': 'ok',
        'endpoints': ['/health', '/test', '/infer'],
        'socketio': socketio is not None
    })

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data'}), 400
        
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data'}), 400
        
        # Simulated response (replace with your YOLO logic)
        response_data = {
            'img': img_data[:100] + "...",
            'meta': {
                'queens': 1,
                'detections': [],
                'timestamp': __import__('time').time()
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        log.error(f"Inference error: {e}")
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    log.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    log.info(f"Client disconnected: {request.sid}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)
else:
    log.info("App created for Gunicorn")