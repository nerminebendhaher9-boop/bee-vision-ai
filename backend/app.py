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

# Replace your current CORS configuration with this:

# CORS configuration - Allow local dev + production
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

# SocketIO configuration - use eventlet for gunicorn compatibility
import os
_is_render = os.environ.get('RENDER', False)
socketio = SocketIO(
    app,
    cors_allowed_origins="*" if _is_render else ["http://localhost:8080", "http://localhost:5173"],
    async_mode='eventlet' if _is_render else 'threading',
    logger=_is_render,
    engineio_logger=_is_render,
    ping_timeout=60,
    ping_interval=25
)

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
            # Camera capture disabled for local dev — frontend sends frames via /infer
            log.info("✅ BeeTracker model loaded (capture disabled)")
        except Exception as e:
            log.error(f"Failed to start tracker: {e}")
            raise
    return tracker

# ── Broadcast thread ──────────────────────────────────────────────────────────
def start_broadcast():
    def broadcast_loop():
        while True:
            try:
                if tracker is not None:
                    frame, meta = tracker.get_latest()
                    if frame is not None:
                        # Resize for broadcast to save bandwidth
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

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "tracker": tracker is not None,
        "socketio": "ready",
        "config": {
            "model_confidence": cfg["model"]["confidence"],
            "fps_target": cfg["camera"]["fps_target"]
        }
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
        # Log incoming request for debugging
        log.info(f"Infer request received")
        log.info(f"Content-Type: {request.content_type}")
        log.info(f"Has JSON: {request.is_json}")
        
        data = request.json
        if not data:
            log.error("No JSON data provided")
            return jsonify({'error': 'No JSON data provided'}), 400
        
        log.info(f"Received keys: {list(data.keys())}")
        
        # Get image data - check both possible keys
        img_data = data.get('img') or data.get('frame')
        
        # Log what we found
        if img_data:
            log.info(f"Image data length: {len(img_data)}")
            log.info(f"First 50 chars: {img_data[:50] if img_data else 'None'}")
        else:
            log.error(f"No image data found. Keys: {list(data.keys())}")
            return jsonify({'error': 'No image data provided. Expected key "img" or "frame"'}), 400
        
        # Check if data is None or empty string
        if img_data is None or img_data == '':
            log.error("Image data is None or empty")
            return jsonify({'error': 'Image data is empty'}), 400
        
        # Handle data URL format
        if ',' in img_data and img_data.startswith('data:image'):
            original_len = len(img_data)
            img_data = img_data.split(',')[1]
            log.info(f"Removed data URL prefix. New length: {len(img_data)} (was {original_len})")
        
        # Validate base64 string looks valid
        if len(img_data) < 100:
            log.error(f"Base64 string too short: {len(img_data)} chars")
            return jsonify({'error': f'Base64 string too short: {len(img_data)} chars'}), 400
        
        # Decode image
        try:
            decoded = base64.b64decode(img_data)
            log.info(f"Decoded {len(decoded)} bytes")
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            log.error(f"Base64 decode error: {e}")
            return jsonify({'error': f'Failed to decode base64: {str(e)}'}), 400
        
        if frame is None:
            log.error("CV2 imdecode returned None - invalid image data")
            return jsonify({'error': 'Failed to decode image - invalid format'}), 400
        
        log.info(f"Frame decoded successfully: {frame.shape}")
        
        # Get tracker and run inference
        try:
            t = get_tracker()
            log.info("Tracker obtained")
        except Exception as e:
            log.error(f"Failed to get tracker: {e}")
            return jsonify({'error': f'Tracker error: {str(e)}'}), 500
        
        # Run YOLO inference
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
            log.info(f"Inference complete. Boxes: {len(res.boxes) if res.boxes else 0}")
        except Exception as e:
            log.error(f"Model prediction error: {e}")
            return jsonify({'error': f'Model inference failed: {str(e)}'}), 500
        
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
                
                # Draw bounding box
                color = cfg["visualization"]["queen_color"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, cfg["visualization"]["bbox_thickness"])
                
                # Draw label
                label = f'{class_name} {conf:.0%}'
                cv2.putText(annotated, label, (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 
                           cfg["visualization"]["font_scale"], 
                           color, 
                           cfg["visualization"]["bbox_thickness"])
        
        # Encode annotated image
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'img': img_b64,
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'inference_ms': 25,
                'timestamp': time.time()
            }
        }
        
        log.info(f"Returning response with {len(detections)} detections")
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
    """Handle frame from client browser for inference"""
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
        
        # Run inference
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
    # Init tracker & broadcast
    get_tracker()
    start_broadcast()
    
    host = cfg["server"]["host"]
    port = cfg["server"]["port_range"][0]
    
    log.info(f"🚀 Starting on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False)
else:
    # For imports (wsgi/gunicorn)
    log.info("App created - will initialize on first request")