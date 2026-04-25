from __future__ import annotations

import sys
import logging
from pathlib import Path
import os
import time
import base64
import threading
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTORCH_NO_CUDA_MEMORY_CACHING'] = '1'
os.environ['YOLO_VERBOSE'] = 'False'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.app")

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import yaml
import cv2
import numpy as np

app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"
app.config['JSON_SORT_KEYS'] = False

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://bee-vision-ai.onrender.com')
ALLOWED_ORIGINS = list(dict.fromkeys([
    FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
]))

CORS(app,
     resources={r"/*": {"origins": ALLOWED_ORIGINS}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

socketio = SocketIO(
    app,
    cors_allowed_origins=ALLOWED_ORIGINS,
    async_mode='gevent',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=5 * 1024 * 1024,
)

def load_config():
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml missing: {cfg_path}")
    with open(cfg_path, encoding='utf-8') as f:
        return yaml.safe_load(f)

cfg = load_config()
log.info("Config loaded")

# ── Model ──────────────────────────────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()
_model_error = None

def _load_model_background():
    global _model, _model_error
    try:
        from ultralytics import YOLO
        w = Path(cfg["model"]["weights"])
        if not w.is_absolute():
            w = ROOT / w
        if not w.exists():
            raise FileNotFoundError(f"Weights not found: {w}")
        log.info("🔄 Loading YOLO model from %s ...", w)
        model = YOLO(str(w), task='detect')
        with _model_lock:
            _model = model
        log.info("✅ Model loaded successfully")
    except Exception as e:
        _model_error = str(e)
        log.error("❌ Model load failed: %s", e)

threading.Thread(target=_load_model_background, daemon=True, name="model-loader").start()

# ── Keep alive ─────────────────────────────────────────────────────────────────
def _keep_alive():
    while True:
        time.sleep(60)
        try:
            port = os.environ.get('PORT', 10000)
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
        except Exception:
            pass

threading.Thread(target=_keep_alive, daemon=True, name="keep-alive").start()

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "Bee AI Pro Backend",
        "status": "running on Render",
        "model_loaded": _model is not None,
        "allowed_origins": ALLOWED_ORIGINS,
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": _model is not None,
        "model_error": _model_error,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'status': 'ok',
        'cors_enabled': True,
        'model_loaded': _model is not None,
    })

@app.route('/stats', methods=['GET'])
def stats():
    return jsonify({
        'queens': 0,
        'model_loaded': _model is not None,
        'running': False,
    })

@app.route('/alerts', methods=['GET'])
def list_alerts():
    try:
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        if alerts_dir.exists():
            alerts = sorted(
                alerts_dir.glob("*.jpg"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
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
    try:
        # Wait up to 180s for model
        waited = 0
        while _model is None and _model_error is None and waited < 180:
            time.sleep(1)
            waited += 1

        if _model_error:
            return jsonify({'error': f'Model failed: {_model_error}'}), 503
        if _model is None:
            return jsonify({'error': 'Model timeout'}), 503

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data'}), 400

        img_data = data.get('img') or data.get('frame')
        if not img_data:
            return jsonify({'error': 'No image data'}), 400

        if isinstance(img_data, str) and ',' in img_data:
            img_data = img_data.split(',', 1)[1]

        missing = len(img_data) % 4
        if missing:
            img_data += '=' * (4 - missing)

        try:
            decoded = base64.b64decode(img_data)
            nparr = np.frombuffer(decoded, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("cv2.imdecode returned None")
        except Exception as e:
            return jsonify({'error': f'Image decode failed: {e}'}), 400

        res = _model.predict(
            frame,
            conf=cfg["model"].get("confidence", 0.75),
            iou=cfg["model"].get("iou", 0.50),
            imgsz=320,
            device="cpu",
            half=False,
            verbose=False,
            classes=[0],
        )[0]

        detections = []
        if res.boxes and len(res.boxes) > 0:
            for box in res.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': round(conf, 3),
                    'class': 'queen'
                })
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 255), 2)
                label = f"queen {conf:.0%}"
                cv2.putText(frame, label, (x1, max(y1 - 8, 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2)

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_b64 = base64.b64encode(buf).decode('utf-8')

        return jsonify({
            'img': img_b64,
            'meta': {
                'queens': len(detections),
                'detections': detections,
                'timestamp': time.time()
            }
        })

    except Exception as e:
        log.error("Inference error: %s", e, exc_info=True)
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    log.info("Client connected: %s", request.sid)
    emit('status', {'connected': True, 'message': 'Bee AI Pro ready!'})

@socketio.on('disconnect')
def handle_disconnect():
    log.info("Client disconnected: %s", request.sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
else:
    log.info("Loaded by gunicorn")