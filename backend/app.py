"""
backend/app.py — BEE AI PRO Main Flask App
Flask + SocketIO + YOLOv8 Queen Detection
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Add root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.app")

import yaml
import cv2
import numpy as np
import base64
import threading
import time
from base64 import b64encode
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime

# Local imports
from detector.tracker import BeeTracker

print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║            Ready for Render Deployment              ║
║                                                      ║
╚══════════════════════════════════════════════════════╝""")

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"

# CORS configuration
PRODUCTION_ORIGIN = "https://bee-vision-ai.onrender.com"

CORS(app, 
     origins=[
         "http://localhost:5173",
         "http://localhost:3000",
         "http://localhost:8080",
         PRODUCTION_ORIGIN
     ],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True)

# ── SocketIO configuration ──────────────────────────────────────────────────────
import os
_is_render = os.environ.get('RENDER', False)

socketio = SocketIO(
    app,
    cors_allowed_origins="*" if _is_render else ["http://localhost:5173", "http://localhost:3000"],
    async_mode='gevent',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10**7,
    http_compression=True
)

log.info(f"SocketIO initialized with async_mode: {socketio.async_mode}")

# ── Config ────────────────────────────────────────────────────────────────────
def load_config() -> Dict[str, Any]:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml missing: {cfg_path}")
    with open(cfg_path, encoding='utf-8') as f:
        return yaml.safe_load(f)

cfg = load_config()
log.info("Config loaded from %s", ROOT / "config.yaml")

# ── Tracker ───────────────────────────────────────────────────────────────────
tracker: BeeTracker = None

def get_tracker() -> BeeTracker:
    global tracker
    if tracker is None:
        try:
            tracker = BeeTracker(cfg)
            log.info("✅ BeeTracker model loaded")
        except Exception as e:
            log.error(f"Failed to start tracker: {e}")
            tracker = None
    return tracker

# ── Broadcast thread ──────────────────────────────────────────────────────────
def start_broadcast():
    def broadcast_loop():
        while True:
            try:
                if tracker is not None:
                    frame, meta = tracker.get_latest()
                    if frame is not None:
                        h, w = frame.shape[:2]
                        if w > 640:
                            scale = 640 / w
                            new_w = 640
                            new_h = int(h * scale)
                            frame = cv2.resize(frame, (new_w, new_h))
                        
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        img_b64 = b64encode(buffer).decode('utf-8')
                        socketio.emit('frame', {'image': img_b64, **meta}, broadcast=True)
                        socketio.emit('stats', tracker.stats, broadcast=True)
                time.sleep(1.0 / cfg["camera"]["fps_target"])
            except Exception as e:
                log.warning("Broadcast error: %s", e)
                time.sleep(0.1)
    
    thread = threading.Thread(target=broadcast_loop, daemon=True, name="broadcast")
    thread.start()
    log.info("✅ Broadcast started")

@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    allowed = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080", PRODUCTION_ORIGIN]
    if origin in allowed:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/stats')
def stats():
    try:
        t = get_tracker()
        return jsonify(t.stats)
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'offline'}), 500

@app.route('/alerts')
def list_alerts():
    try:
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        if alerts_dir.exists():
            alerts = sorted(alerts_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            return jsonify([p.name for p in alerts[:50]])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/alerts/<filename>')
def get_alert(filename):
    try:
        return send_from_directory(ROOT / cfg["alerts"]["save_dir"], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return '', 200
    
    # Vérifier le statut du tracker
    tracker_status = tracker is not None
    
    return jsonify({
        "status": "ok",
        "socketio": "ready",
        "tracker": tracker_status,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    return jsonify({
        'status': 'ok',
        'endpoints': ['/alerts', '/stats', '/infer', '/health', '/test'],
        'socketio': socketio is not None,
        'tracker': tracker is not None,
        'config_loaded': True
    })

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        img_data = data.get('img') or data.get('frame')
        
        if not img_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Handle data URL format - remove prefix if present
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Decode image
        try:
            decoded = base64.b64decode(img_data)
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            log.error(f"Base64 decode error: {e}")
            return jsonify({'error': f'Failed to decode base64: {str(e)}'}), 400
        
        if frame is None:
            return jsonify({'error': 'Failed to decode image'}), 400
        
        # Get tracker and run inference
        t = get_tracker()
        
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
        
        # Annotate frame
        annotated = frame.copy()
        detections = []
        
        if res.boxes and len(res.boxes) > 0:
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0])
                class_name = cfg["classes"].get(cls, f"class_{cls}")
                
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': float(conf),
                    'class': class_name,
                    'class_id': cls
                })
                
                color = cfg["visualization"]["queen_color"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, cfg["visualization"]["bbox_thickness"])
                
                label = f'{class_name} {conf:.0%}'
                cv2.putText(annotated, label, (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 
                           cfg["visualization"]["font_scale"], 
                           color, 
                           cfg["visualization"]["bbox_thickness"])
        
        # Encode annotated image - return ONLY base64 (no prefix)
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'img': img_b64,  # ← Only base64, no data:image prefix
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time()
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ── Socket events ─────────────────────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    log.info("Client connected: %s", request.sid)
    emit('status', {'connected': True, 'message': 'Bee AI Pro ready!', 'config': {
        'fps': cfg["camera"]["fps_target"],
        'confidence': cfg["model"]["confidence"]
    }})

@socketio.on('disconnect')
def handle_disconnect():
    log.info("Client disconnected: %s", request.sid)

@socketio.on('client_frame')
def handle_client_frame(data):
    try:
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            emit('error', {'message': 'No image data'})
            return
        
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        nparr = np.frombuffer(base64.b64decode(img_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('error', {'message': 'Failed to decode image'})
            return
        
        t = get_tracker()
        res = t.model.predict(frame, conf=cfg["model"]["confidence"], verbose=False)[0]
        
        detections = []
        if len(res.boxes) > 0:
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = box.conf[0].cpu().numpy()
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': float(conf)
                })
        
        emit('inference_result', {'detections': detections, 'count': len(detections)})
        
    except Exception as e:
        log.error(f"Client frame error: {e}")
        emit('error', {'message': str(e)})

# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    get_tracker()
    start_broadcast()
    
    host = cfg["server"]["host"]
    port = cfg["server"]["port_range"][0]
    
    log.info(f"🚀 Starting on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False)
else:
    log.info("App created - will initialize on first request")