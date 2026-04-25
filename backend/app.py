"""
BEE AI PRO - Complete Backend for Render
Fixed for Render Free Tier with proper CORS
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
import os
import time
import base64
import threading
from datetime import datetime
from base64 import b64encode

# Add root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Memory optimization for Render Free Tier
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTORCH_NO_CUDA_MEMORY_CACHING'] = '1'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.app")

# Flask imports
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import yaml
import cv2
import numpy as np

print("""
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║          Deployed on Render - Optimized             ║
╚══════════════════════════════════════════════════════╝""")

# ──────────────────────────────────────────────────────────────────────────────
# FLASK APP INITIALIZATION
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"
app.config['JSON_SORT_KEYS'] = False

# ──────────────────────────────────────────────────────────────────────────────
# CORS CONFIGURATION - COMPLETE FIX FOR RENDER
# ──────────────────────────────────────────────────────────────────────────────

# Get frontend URL from environment or use default
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://bee-vision-ai.onrender.com')

# Allow all Render frontend domains and local development
ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "https://bee-vision-ai.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080"
]

# Configure CORS
CORS(app, 
     resources={r"/*": {"origins": ALLOWED_ORIGINS}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

@app.after_request
def add_cors_headers(response):
    """Add CORS headers to every response"""
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# ──────────────────────────────────────────────────────────────────────────────
# SOCKETIO CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

socketio = SocketIO(
    app,
    cors_allowed_origins=ALLOWED_ORIGINS,
    async_mode='gevent',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=5 * 1024 * 1024,
    http_compression=True
)

log.info(f"SocketIO initialized with async_mode: {socketio.async_mode}")

# ──────────────────────────────────────────────────────────────────────────────
# LOAD CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

def load_config():
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml missing: {cfg_path}")
    with open(cfg_path, encoding='utf-8') as f:
        return yaml.safe_load(f)

cfg = load_config()
log.info("Config loaded from %s", ROOT / "config.yaml")

# ──────────────────────────────────────────────────────────────────────────────
# TRACKER (Lazy Loaded for Memory Efficiency)
# ──────────────────────────────────────────────────────────────────────────────

tracker = None
tracker_lock = threading.Lock()

def get_tracker():
    """Lazy load tracker only when needed"""
    global tracker
    if tracker is None:
        with tracker_lock:
            if tracker is None:
                try:
                    from detector.tracker import BeeTracker
                    log.info("Loading BeeTracker...")
                    tracker = BeeTracker(cfg)
                    tracker.start()
                    log.info("✅ BeeTracker loaded successfully")
                except Exception as e:
                    log.error(f"Failed to start tracker: {e}")
                    tracker = None
    return tracker

# ──────────────────────────────────────────────────────────────────────────────
# OPTIONS HANDLER
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/infer', methods=['OPTIONS'])
@app.route('/stats', methods=['OPTIONS'])
@app.route('/health', methods=['OPTIONS'])
@app.route('/test', methods=['OPTIONS'])
@app.route('/alerts', methods=['OPTIONS'])
def handle_options():
    """Handle preflight OPTIONS requests"""
    response = jsonify({'status': 'ok'})
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response, 200

# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    t = get_tracker()
    return jsonify({
        "status": "ok" if t else "degraded",
        "tracker_ready": t is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'status': 'ok',
        'message': 'CORS is working! Backend is alive.',
        'cors_enabled': True,
        'allowed_origins': ALLOWED_ORIGINS,
        'tracker_loaded': tracker is not None
    })

@app.route('/stats', methods=['GET'])
def stats():
    try:
        t = get_tracker()
        if t and hasattr(t, 'stats'):
            return jsonify(t.stats)
        return jsonify({'error': 'Tracker not ready', 'queens': 0}), 503
    except Exception as e:
        log.error(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/alerts', methods=['GET'])
def list_alerts():
    try:
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        if alerts_dir.exists():
            alerts = sorted(alerts_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            return jsonify([p.name for p in alerts[:50]])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/alerts/<filename>', methods=['GET'])
def get_alert(filename):
    try:
        return send_from_directory(ROOT / cfg["alerts"]["save_dir"], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/infer', methods=['POST'])
def infer():
    """Inference endpoint with CORS support"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Remove data URL prefix
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Fix base64 padding
        missing_padding = len(img_data) % 4
        if missing_padding:
            img_data += '=' * (4 - missing_padding)
        
        # Decode image
        try:
            decoded = base64.b64decode(img_data)
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            return jsonify({'error': f'Failed to decode image: {str(e)}'}), 400
        
        t = get_tracker()
        if t is None:
            return jsonify({'error': 'Tracker not available'}), 503
        
        # Run inference
        res = t.model.predict(
            frame,
            conf=cfg["model"].get("confidence", 0.75),
            iou=cfg["model"].get("iou", 0.50),
            imgsz=cfg["model"].get("imgsz", 320),
            device="cpu",
            half=False,
            verbose=False,
            classes=[0]
        )[0]
        
        detections = []
        if res.boxes and len(res.boxes) > 0:
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf,
                    'class': 'queen'
                })
        
        return jsonify({
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time()
            }
        })
        
    except Exception as e:
        log.error(f"Inference error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "Bee AI Pro Backend",
        "status": "running on Render",
        "cors_enabled": True,
        "allowed_origins": ALLOWED_ORIGINS,
        "endpoints": ["/health", "/test", "/stats", "/alerts", "/infer"]
    })

# ──────────────────────────────────────────────────────────────────────────────
# SOCKETIO EVENTS
# ──────────────────────────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    log.info(f"Client connected: {request.sid}")
    emit('status', {'connected': True, 'message': 'Bee AI Pro ready!'})

@socketio.on('disconnect')
def handle_disconnect():
    log.info(f"Client disconnected: {request.sid}")

# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    log.info(f"🚀 Starting on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
else:
    log.info("App loaded by gunicorn")