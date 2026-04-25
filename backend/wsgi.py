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

from app import app, socketio

application = app