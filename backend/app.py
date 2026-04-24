"""
backend/app.py — BEE AI PRO Main Flask App
Flask + SocketIO + YOLOv8 Queen Detection
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

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import yaml
import cv2
import numpy as np
import base64
import time
from datetime import datetime

# Local imports
from detector.tracker import BeeTracker

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
# CORS CONFIGURATION - SINGLE SOURCE OF TRUTH
# ============================================================
ALLOWED_ORIGINS = [
    "https://bee-vision-ai.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080"
]

CORS(app, 
     origins=ALLOWED_ORIGINS,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True)

# ============================================================
# SOCKETIO CONFIGURATION
# ============================================================
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
# CONFIGURATION LOADING
# ============================================================
def load_config():
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        log.error(f"Config not found at {cfg_path}")
        return None
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

cfg = load_config()
if cfg:
    log.info("Config loaded successfully")

# ============================================================
# TRACKER INITIALIZATION
# ============================================================
tracker = None

def get_tracker():
    global tracker
    if tracker is None and cfg:
        try:
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
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "socketio": "ready",
        "tracker": tracker is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test', methods=['GET', 'OPTIONS'])
def test():
    """Test endpoint listing available routes"""
    return jsonify({
        'status': 'ok',
        'endpoints': ['/health', '/test', '/infer', '/stats', '/alerts'],
        'socketio': socketio is not None,
        'tracker': tracker is not None,
        'config_loaded': cfg is not None
    })

@app.route('/stats', methods=['GET', 'OPTIONS'])
def stats():
    """Return tracker statistics"""
    t = get_tracker()
    if t:
        return jsonify(t.stats)
    return jsonify({'error': 'Tracker not available', 'status': 'offline'}), 503

@app.route('/alerts', methods=['GET', 'OPTIONS'])
def list_alerts():
    """List saved alert images"""
    if not cfg:
        return jsonify({'error': 'Configuration not loaded'}), 500
    try:
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        if alerts_dir.exists():
            alerts = sorted(alerts_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            return jsonify([p.name for p in alerts[:50]])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/alerts/<filename>', methods=['GET', 'OPTIONS'])
def get_alert(filename):
    """Serve alert image"""
    if not cfg:
        return jsonify({'error': 'Configuration not loaded'}), 500
    try:
        from flask import send_from_directory
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        return send_from_directory(alerts_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    """Main inference endpoint - receives image, returns detections"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Get image data
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Remove data URL prefix if present
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Fix base64 padding
        missing_padding = len(img_data) % 4
        if missing_padding:
            img_data += '=' * (4 - missing_padding)
        
        # Decode base64 to image
        try:
            decoded = base64.b64decode(img_data)
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            log.error(f"Base64 decode error: {e}")
            return jsonify({'error': f'Failed to decode image: {str(e)}'}), 400
        
        if frame is None:
            return jsonify({'error': 'Invalid image data'}), 400
        
        # Get tracker and run inference
        t = get_tracker()
        detections = []
        annotated = frame.copy()
        
        if t is not None and cfg:
            try:
                # Run YOLO inference
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
                
                # Process detections
                if res.boxes and len(res.boxes) > 0:
                    for box in res.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0].cpu().numpy())
                        cls = int(box.cls[0])
                        class_name = cfg["classes"].get(cls, f"class_{cls}")
                        
                        detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': conf,
                            'class': class_name,
                            'class_id': cls
                        })
                        
                        # Draw bounding box
                        color = cfg["visualization"]["queen_color"]
                        thickness = cfg["visualization"]["bbox_thickness"]
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
                        
                        # Draw label
                        label = f'{class_name} {conf:.0%}'
                        font_scale = cfg["visualization"]["font_scale"]
                        cv2.putText(annotated, label, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
                
                log.info(f"Inference complete: {len(detections)} queens detected")
                
            except Exception as e:
                log.error(f"YOLO inference error: {e}")
                # Return unannotated frame if inference fails
        
        # Encode response image (always return something)
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'img': f'data:image/jpeg;base64,{img_b64}',  # Proper data URL format
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time(),
                'processing_time_ms': 0  # Add actual timing if desired
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

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

@socketio.on('ping')
def handle_ping():
    emit('pong')

# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    # Initialize tracker on startup
    get_tracker()
    
    host = "0.0.0.0"
    port = int(os.environ.get('PORT', 10000))
    
    log.info(f"🚀 Starting BEE AI PRO on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False)
else:
    # For Gunicorn
    log.info("App created for Gunicorn - will initialize on first request")