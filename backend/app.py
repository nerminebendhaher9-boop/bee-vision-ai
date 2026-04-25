"""
BEE AI PRO - Complete Backend Application
Fixed for Render Free Tier (512MB RAM) with proper CORS
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
║       Optimized for Render Free Tier (512MB)        ║
╚══════════════════════════════════════════════════════╝""")

# ──────────────────────────────────────────────────────────────────────────────
# FLASK APP INITIALIZATION
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"
app.config['JSON_SORT_KEYS'] = False  # Slightly better performance

# ──────────────────────────────────────────────────────────────────────────────
# CORS CONFIGURATION - COMPLETE FIX
# ──────────────────────────────────────────────────────────────────────────────

# Allow your frontend domains
ALLOWED_ORIGINS = [
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

# Add CORS headers after every request
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
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
    max_http_buffer_size=5 * 1024 * 1024,  # 5MB limit
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
broadcast_thread = None

def get_tracker():
    """Lazy load tracker only when needed to save memory"""
    global tracker
    if tracker is None:
        with tracker_lock:
            if tracker is None:
                try:
                    from detector.tracker import BeeTracker
                    log.info("Loading BeeTracker (this may take a moment)...")
                    tracker = BeeTracker(cfg)
                    tracker.start()
                    log.info("✅ BeeTracker loaded successfully")
                    
                    # Log memory usage after loading
                    try:
                        import psutil
                        process = psutil.Process()
                        mem_mb = process.memory_info().rss / 1024 / 1024
                        log.info(f"Memory after tracker load: {mem_mb:.0f}MB")
                    except:
                        pass
                        
                except Exception as e:
                    log.error(f"Failed to start tracker: {e}")
                    tracker = None
    return tracker

# ──────────────────────────────────────────────────────────────────────────────
# BROADCAST THREAD (For SocketIO streaming)
# ──────────────────────────────────────────────────────────────────────────────

def start_broadcast():
    global broadcast_thread
    if broadcast_thread and broadcast_thread.is_alive():
        return
    
    def broadcast_loop():
        log.info("Broadcast loop started")
        last_memory_log = time.time()
        
        while True:
            try:
                t = get_tracker()
                if t is not None:
                    frame, meta = t.get_latest()
                    if frame is not None:
                        # Resize to reduce bandwidth
                        h, w = frame.shape[:2]
                        if w > 640:
                            scale = 640 / w
                            new_w = 640
                            new_h = int(h * scale)
                            frame = cv2.resize(frame, (new_w, new_h))
                        
                        # Encode to JPEG
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        img_b64 = b64encode(buffer).decode('utf-8')
                        
                        # Emit to all connected clients
                        socketio.emit('frame', {'image': img_b64, **meta}, broadcast=True)
                        socketio.emit('stats', t.stats, broadcast=True)
                        
                        # Log memory every 30 seconds
                        now = time.time()
                        if now - last_memory_log > 30:
                            last_memory_log = now
                            if 'psutil' in sys.modules:
                                import psutil
                                process = psutil.Process()
                                mem_mb = process.memory_info().rss / 1024 / 1024
                                log.info(f"Memory usage: {mem_mb:.0f}MB")
                                
                                # Force GC if memory too high
                                if mem_mb > 450:
                                    log.warning("Memory high, forcing garbage collection")
                                    import gc
                                    gc.collect()
                
                # Control frame rate
                time.sleep(1.0 / cfg["camera"].get("fps_target", 5))
                
            except Exception as e:
                log.warning(f"Broadcast error: {e}")
                time.sleep(1)
    
    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True, name="broadcast")
    broadcast_thread.start()
    log.info("✅ Broadcast thread started")

# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    t = get_tracker()
    status = "ok" if t is not None else "degraded"
    
    return jsonify({
        "status": status,
        "tracker_ready": t is not None,
        "timestamp": datetime.now().isoformat(),
        "uptime": time.time() - app.config.get('START_TIME', time.time())
    })

# ──────────────────────────────────────────────────────────────────────────────
# TEST ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/test', methods=['GET', 'OPTIONS'])
def test():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    return jsonify({
        'status': 'ok',
        'message': 'CORS is working! Backend is alive.',
        'endpoints': ['/alerts', '/stats', '/infer', '/health', '/test'],
        'socketio': socketio is not None,
        'tracker': tracker is not None,
        'timestamp': datetime.now().isoformat()
    })

# ──────────────────────────────────────────────────────────────────────────────
# STATS ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/stats', methods=['GET', 'OPTIONS'])
def stats():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    try:
        t = get_tracker()
        if t and hasattr(t, 'stats'):
            return jsonify(t.stats)
        else:
            return jsonify({
                'error': 'Tracker not ready',
                'status': 'initializing',
                'queens': 0,
                'fps': 0
            }), 503
    except Exception as e:
        log.error(f"Stats error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

# ──────────────────────────────────────────────────────────────────────────────
# ALERTS ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/alerts', methods=['GET', 'OPTIONS'])
def list_alerts():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    try:
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        if alerts_dir.exists():
            alerts = sorted(alerts_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            return jsonify([p.name for p in alerts[:50]])
        return jsonify([])
    except Exception as e:
        log.error(f"Alerts list error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/alerts/<filename>', methods=['GET', 'OPTIONS'])
def get_alert(filename):
    if request.method == 'OPTIONS':
        return _handle_options()
    
    try:
        return send_from_directory(ROOT / cfg["alerts"]["save_dir"], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# ──────────────────────────────────────────────────────────────────────────────
# INFERENCE ENDPOINT (Complete with CORS)
# ──────────────────────────────────────────────────────────────────────────────

def _handle_options():
    """Handle preflight OPTIONS requests"""
    response = jsonify({'status': 'ok'})
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response, 200

@app.route('/infer', methods=['POST', 'OPTIONS'])
def infer():
    """Complete inference endpoint with proper CORS handling"""
    
    # Handle preflight request
    if request.method == 'OPTIONS':
        return _handle_options()
    
    # Validate request
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 415
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    # Get image data
    img_data = data.get('img') or data.get('frame')
    if not img_data:
        return jsonify({'error': 'No image data provided (field "img" or "frame" required)'}), 400
    
    # Remove data URL prefix if present
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
        if frame is None:
            raise ValueError("Could not decode image")
    except Exception as e:
        log.error(f"Base64 decode error: {e}")
        return jsonify({'error': f'Failed to decode base64: {str(e)}'}), 400
    
    # Get tracker and run inference
    t = get_tracker()
    if t is None:
        return jsonify({'error': 'Tracker not available (still initializing)'}), 503
    
    try:
        # Run YOLO inference
        res = t.model.predict(
            frame,
            conf=cfg["model"].get("confidence", 0.75),
            iou=cfg["model"].get("iou", 0.50),
            imgsz=cfg["model"].get("imgsz", 320),
            device="cpu",
            half=False,
            verbose=False,
            classes=[0],
            max_det=10
        )[0]
        
        # Annotate frame and collect detections
        annotated = frame.copy()
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
                
                # Draw bounding box
                color = cfg["visualization"].get("queen_color", [0, 180, 255])
                thickness = cfg["visualization"].get("bbox_thickness", 2)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
                
                # Draw label
                label = f'queen {conf:.0%}'
                font_scale = cfg["visualization"].get("font_scale", 0.5)
                cv2.putText(annotated, label, (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX,
                           font_scale,
                           color,
                           thickness)
        
        # Encode annotated image
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Build response
        response_data = {
            'img': img_b64,
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time()
            }
        }
        
        # Return with CORS headers
        response = jsonify(response_data)
        origin = request.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            response.headers.add('Access-Control-Allow-Origin', origin)
        
        return response
        
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ──────────────────────────────────────────────────────────────────────────────
# SOCKETIO EVENT HANDLERS
# ──────────────────────────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    log.info(f"Client connected: {request.sid}")
    emit('status', {
        'connected': True,
        'message': 'Bee AI Pro ready!',
        'config': {
            'fps': cfg["camera"].get("fps_target", 5),
            'confidence': cfg["model"].get("confidence", 0.75)
        }
    })

@socketio.on('disconnect')
def handle_disconnect():
    log.info(f"Client disconnected: {request.sid}")

@socketio.on('client_frame')
def handle_client_frame(data):
    """Handle frame from client for inference via WebSocket"""
    try:
        img_data = data.get('img') or data.get('frame')
        if not img_data:
            emit('error', {'message': 'No image data'})
            return
        
        # Remove data URL prefix if present
        if ',' in img_data and img_data.startswith('data:image'):
            img_data = img_data.split(',')[1]
        
        # Fix base64 padding
        missing_padding = len(img_data) % 4
        if missing_padding:
            img_data += '=' * (4 - missing_padding)
        
        nparr = np.frombuffer(base64.b64decode(img_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('error', {'message': 'Failed to decode image'})
            return
        
        t = get_tracker()
        if t is None:
            emit('error', {'message': 'Tracker not available'})
            return
        
        res = t.model.predict(frame, conf=cfg["model"]["confidence"], verbose=False)[0]
        
        detections = []
        if res.boxes and len(res.boxes) > 0:
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf
                })
        
        emit('inference_result', {
            'detections': detections,
            'count': len(detections)
        })
        
    except Exception as e:
        log.error(f"Client frame error: {e}")
        emit('error', {'message': str(e)})

# ──────────────────────────────────────────────────────────────────────────────
# ROOT ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "Bee AI Pro Backend",
        "version": "1.0.0",
        "status": "running",
        "cors_enabled": True,
        "allowed_origins": ALLOWED_ORIGINS,
        "endpoints": ["/health", "/test", "/stats", "/alerts", "/infer"],
        "websocket": "/socket.io",
        "timestamp": datetime.now().isoformat()
    })

# ──────────────────────────────────────────────────────────────────────────────
# APPLICATION STARTUP
# ──────────────────────────────────────────────────────────────────────────────

# Store start time for uptime tracking
app.config['START_TIME'] = time.time()

if __name__ == '__main__':
    # Running directly (not via gunicorn)
    port = int(os.environ.get('PORT', 10000))
    host = cfg["server"].get("host", "0.0.0.0")
    
    log.info(f"🚀 Starting BEE AI PRO on http://{host}:{port}")
    
    # Start broadcast thread
    start_broadcast()
    
    # Run the app
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
else:
    # Running via gunicorn (production)
    log.info("App loaded by gunicorn, starting broadcast thread...")
    
    # Start broadcast thread for production
    start_broadcast()
    
    log.info("✅ Application ready for gunicorn")