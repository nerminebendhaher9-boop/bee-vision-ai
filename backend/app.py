from __future__ import annotations

# ✅ MUST be first
from gevent import monkey
monkey.patch_all()

import sys
import logging
from pathlib import Path
import os
import time
import base64
import threading
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ✅ Environment optimizations
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["YOLO_VERBOSE"] = "False"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.app")

from flask import Flask, request, jsonify, make_response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import yaml
import cv2
import numpy as np

# ─────────────────────────────────────────────
# FLASK INIT
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "bee-ai-pro-secret"
app.config["JSON_SORT_KEYS"] = False

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://bee-vision-ai.onrender.com")

ALLOWED_ORIGINS = list(dict.fromkeys([
    FRONTEND_URL,
    "https://bee-vision-ai.onrender.com",
    "https://bee-vision-ai-b.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
]))

CORS(
    app,
    resources={r"/*": {
        "origins": ALLOWED_ORIGINS,
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    }}
)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            resp = make_response()
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            resp.headers["Access-Control-Max-Age"] = "86400"
            return resp

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

socketio = SocketIO(
    app,
    cors_allowed_origins=ALLOWED_ORIGINS,
    async_mode="gevent",
    ping_timeout=60,
    ping_interval=25,
)

# ─────────────────────────────────────────────
# LOAD CONFIG
# ─────────────────────────────────────────────
def load_config():
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml missing: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()
log.info("✅ Config loaded")

# ─────────────────────────────────────────────
# MODEL (SAFE LOADING)
# ─────────────────────────────────────────────
_model = None
_model_error = None


def load_model():
    global _model, _model_error
    try:
        from ultralytics import YOLO

        w = Path(cfg["model"]["weights"])
        if not w.is_absolute():
            w = ROOT / w

        if not w.exists():
            raise FileNotFoundError(f"Weights not found: {w}")

        size_mb = round(w.stat().st_size / 1024 / 1024, 1)
        log.info(f"🔄 Loading model ({size_mb} MB)...")

        _model = YOLO(str(w), task="detect")

        log.info("✅ Model loaded")

    except Exception as e:
        _model_error = str(e)
        log.error("❌ Model failed: %s", e, exc_info=True)


# ✅ Load model in background (non-blocking)
threading.Thread(target=load_model, daemon=True).start()

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "status": "running",
        "model_loaded": _model is not None,
        "error": _model_error
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": _model is not None,
        "timestamp": datetime.now().isoformat()
    })


@app.route("/infer", methods=["POST"])
def infer():
    try:
        if _model_error:
            return jsonify({"error": _model_error}), 503

        if _model is None:
            return jsonify({"error": "Model loading"}), 503

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON"}), 400

        img_data = data.get("img") or data.get("frame")
        if not img_data:
            return jsonify({"error": "No image"}), 400

        # Base64 clean
        if "," in img_data:
            img_data = img_data.split(",", 1)[1]

        # Fix padding
        img_data += "=" * (-len(img_data) % 4)

        decoded = base64.b64decode(img_data)
        np_arr = np.frombuffer(decoded, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"error": "Invalid image"}), 400

        # Inference
        m = cfg["model"]

        results = _model.predict(
            frame,
            conf=m.get("confidence", 0.7),
            iou=m.get("iou", 0.5),
            imgsz=m.get("imgsz", 320),
            device="cpu",
            verbose=False,
            classes=None  # ✅ FIXED
        )[0]

        detections = []

        if results.boxes:
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(conf, 3),
                    "class": "queen"
                })

                # Draw
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 255), 2)
                cv2.putText(frame, f"{conf:.0%}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2)

        _, buffer = cv2.imencode(".jpg", frame)
        img_out = base64.b64encode(buffer).decode("utf-8")

        return jsonify({
            "img": img_out,
            "meta": {
                "count": len(detections),
                "detections": detections,
                "time": time.time()
            }
        })

    except Exception as e:
        log.error("❌ Inference error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# SOCKETIO
# ─────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    emit("status", {"connected": True})


@socketio.on("disconnect")
def on_disconnect():
    pass


# ─────────────────────────────────────────────
# RUN (LOCAL ONLY)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)