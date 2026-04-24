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
import yaml
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

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"

# ============================================================
# CORS CONFIGURATION - DEFINITIVE
# ============================================================
CORS(app, origins=["https://bee-vision-ai.onrender.com", "http://localhost:5173", "http://localhost:3000"])

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# ============================================================
# SOCKETIO
# ============================================================
_is_render = os.environ.get('RENDER', False)

socketio = SocketIO(
    app,
    cors_allowed_origins="https://bee-vision-ai.onrender.com",
    async_mode='gevent',
    logger=False,
    engineio_logger=False
)

log.info("SocketIO initialized")

# ============================================================
# CONFIG & TRACKER
# ============================================================
def load_config():
    cfg_path = ROOT / "config.yaml"
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

cfg = load_config()
log.info("Config loaded")

# Importer le tracker seulement quand nécessaire
tracker = None

def get_tracker():
    global tracker
    if tracker is None:
        try:
            from detector.tracker import BeeTracker
            tracker = BeeTracker(cfg)
            log.info("✅ BeeTracker model loaded successfully")
        except Exception as e:
            log.error(f"Failed to load tracker: {e}")
            tracker = None
    return tracker

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
        "tracker": tracker is not None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    })

@app.route('/test', methods=['GET', 'OPTIONS'])
def test():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({
        'status': 'ok',
        'endpoints': ['/health', '/test', '/infer'],
        'socketio': socketio is not None,
        'tracker': tracker is not None
    })

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    if request.method == 'OPTIONS':
        response = Response('')
        response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return response, 200
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data'}), 400
        
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data'}), 400
        
        # Enlever le préfixe data:image si présent
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Correction du padding base64
        missing_padding = len(img_data) % 4
        if missing_padding:
            img_data += '=' * (4 - missing_padding)
        
        # Décoder l'image
        decoded = base64.b64decode(img_data)
        nparr = np.frombuffer(decoded, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Invalid image'}), 400
        
        # Obtenir le tracker et exécuter l'inférence
        t = get_tracker()
        detections = []
        annotated = frame.copy()
        
        if t is not None:
            try:
                res = t.model.predict(
                    frame,
                    conf=cfg["model"]["confidence"],
                    iou=cfg["model"]["iou"],
                    imgsz=cfg["model"]["imgsz"],
                    device=cfg["model"]["device"],
                    half=cfg["model"]["half"],
                    classes=[0],
                    verbose=False
                )[0]
                
                if res.boxes and len(res.boxes) > 0:
                    for box in res.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0].cpu().numpy())
                        
                        detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': conf,
                            'class': 'queen',
                            'class_id': 0
                        })
                        
                        # Dessiner le rectangle
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 180, 255), 2)
                        label = f'queen {conf:.0%}'
                        cv2.putText(annotated, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2)
                
                log.info(f"Inference: {len(detections)} queens detected")
                
            except Exception as e:
                log.error(f"YOLO inference error: {e}")
        
        # Encoder l'image annotée
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'img': f'data:image/jpeg;base64,{img_b64}',
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time()
            }
        }
        
        response = jsonify(response_data)
        response.headers['Access-Control-Allow-Origin'] = 'https://bee-vision-ai.onrender.com'
        return response
        
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
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
    # Initialiser le tracker au démarrage
    get_tracker()
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
else:
    log.info("App created for Gunicorn")