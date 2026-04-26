from gevent import monkey
monkey.patch_all(thread=False)

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['PYTHONMALLOC'] = 'malloc'
os.environ['PYTORCH_NO_CUDA_MEMORY_CACHING'] = '1'
os.environ['YOLO_VERBOSE'] = 'False'

# Load model BEFORE gunicorn starts — avoids thread/gevent issues
print("⏳ Loading YOLO model...")
try:
    from ultralytics import YOLO
    from pathlib import Path as P
    import yaml
    cfg = yaml.safe_load(open(backend_dir / "config.yaml"))
    w = P(cfg["model"]["weights"])
    if not w.is_absolute():
        w = backend_dir / w
    _preloaded_model = YOLO(str(w), task='detect')
    print(f"✅ Model loaded ({round(w.stat().st_size/1024/1024, 1)} MB)")
except Exception as e:
    _preloaded_model = None
    print(f"❌ Model load failed: {e}")

from app import app, socketio
import app as app_module

# Inject preloaded model into app module
if _preloaded_model is not None:
    app_module._model = _preloaded_model

application = app