"""
backend/app.py — BEE AI PRO Main Flask App
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.app")

from flask import Flask, jsonify, request, Response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import cv2
import numpy as np
import base64
import time
import os

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║            Ready for Render Deployment              ║
╚══════════════════════════════════════════════════════╝""")

# ============================================================
# APP INITIALIZATION
# ============================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"

# ============================================================
# CORS CONFIGURATION - FORCE HEADERS
# ============================================================
CORS(app, origins=["https://bee-vision-ai.onrender.com", "http://localhost:5173", "http://localhost:3000"])

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# ============================================================
# SOCKETIO (Fonctionne avec wsgi.py)
# ============================================================
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

log.info("SocketIO initialized")

# ============================================================
# ROUTES
# ============================================================
@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({
        "status": "ok",
        "socketio": "ready",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    })

@app.route('/test', methods=['GET', 'OPTIONS'])
def test():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({
        'status': 'ok',
        'endpoints': ['/health', '/test', '/infer'],
        'socketio': socketio is not None
    })

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    if request.method == 'OPTIONS':
        response = Response('')
        response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return response, 200
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data'}), 400
        
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data'}), 400
        
        # Supprimer le préfixe data:image si présent
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Décoder l'image
        try:
            decoded = base64.b64decode(img_data)
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except:
            # Si l'image est invalide, utiliser une image de test
            frame = np.ones((480, 640, 3), dtype=np.uint8) * 240
            cv2.putText(frame, "Bee AI Pro", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Traitement simple (rectangle de détection simulé)
        if frame is not None:
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (w//4, h//4), (3*w//4, 3*h//4), (0, 0, 255), 3)
            cv2.putText(frame, "Queen Detected", (w//4, h//4 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Encoder la réponse
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'img': f'data:image/jpeg;base64,{img_b64}',
            'meta': {
                'queens': 1,
                'detections': [],
                'timestamp': time.time()
            }
        }
        
        response = jsonify(response_data)
        response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
        return response
        
    except Exception as e:
        log.error(f"Inference error: {e}")
        response = jsonify({'error': str(e)})
        response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
        return response, 500

# ============================================================
# SOCKETIO EVENTS
# ============================================================
@socketio.on('connect')
def handle_connect():
    log.info(f"Client connected: {request.sid}")
    emit('status', {'connected': True, 'message': 'Bee AI Pro ready!'})

@socketio.on('disconnect')
def handle_disconnect():
    log.info(f"Client disconnected: {request.sid}")

# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
else:
    log.info("App created for Gunicorn")