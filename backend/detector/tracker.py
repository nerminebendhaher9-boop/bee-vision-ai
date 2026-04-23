"""
detector/tracker.py  —  BEE AI PRO
YOLOv8m + ByteTrack  |  queen detection only (class 0)
Thread-safe, Windows-compatible, Render-ready
"""
from __future__ import annotations

import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
log  = logging.getLogger("bee.tracker")

QUEEN_BGR = (0, 180, 255)   # amber
HUD_BG    = (12, 14, 18)


class BeeTracker:
    def __init__(self, cfg: dict) -> None:
        self.cfg         = cfg
        self._lock       = threading.Lock()
        self._latest     = (None, {})
        self._running    = False
        self._thread     = None
        self._last_saved: dict[int, float] = defaultdict(float)
        self._load_model()
        self._init_tracker()
        alerts_dir = ROOT / cfg["alerts"]["save_dir"]
        alerts_dir.mkdir(parents=True, exist_ok=True)
        self._alerts_dir = alerts_dir
        self.stats = {
            "fps": 0.0, "queens": 0, "total_tracks": 0,
            "alerts_saved": 0, "uptime_s": 0, "running": False,
        }
        self._start_time = time.time()

    # ── model ─────────────────────────────────────────────────────────────────
    def _load_model(self):
        from ultralytics import YOLO
        w = Path(self.cfg["model"]["weights"])
        if not w.is_absolute():
            w = ROOT / w
        
        if not w.exists():
            raise FileNotFoundError(
                f"Weights not found: {w}\n"
                "Copy your trained best.pt → backend/models/weights/best.pt"
            )
        # Load with task='detect' for better cross-version compatibility
        self.model        = YOLO(str(w), task='detect')
        self.model_device = self.cfg["model"].get("device", "") or ""
        log.info("Model loaded: %s", w.name)

    # ── tracker ───────────────────────────────────────────────────────────────
    def _init_tracker(self):
        import supervision as sv
        t = self.cfg["tracking"]
        
        # Handle different ByteTrack versions
        try:
            # Newer supervision versions
            self._tracker = sv.ByteTrack(
                track_activation_threshold=t.get("track_high_thresh", 0.50),
                lost_track_buffer=t.get("track_buffer", 30),
                minimum_matching_threshold=t.get("match_thresh", 0.80),
                frame_rate=self.cfg["camera"].get("fps_target", 30)
            )
        except (AttributeError, TypeError):
            try:
                # Older supervision versions
                from supervision.tracker.byte_tracker import ByteTrack
                self._tracker = ByteTrack(
                    track_thresh=t.get("track_high_thresh", 0.50),
                    track_buffer=t.get("track_buffer", 30),
                    match_thresh=t.get("match_thresh", 0.80),
                    frame_rate=self.cfg["camera"].get("fps_target", 30)
                )
            except (ImportError, AttributeError):
                # Fallback - create custom tracker
                self._tracker = None
                log.warning("ByteTrack not available, using simple detection")
        
        log.info("Tracker initialized")

    # ── public API ────────────────────────────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._running = True
        self.stats["running"] = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="bee-capture"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        self.stats["running"] = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_latest(self) -> tuple:
        with self._lock:
            f, m = self._latest
            return (f.copy() if f is not None else None), dict(m)

    # ── capture loop ──────────────────────────────────────────────────────────
    def _loop(self):
        import supervision as sv
        cam = self.cfg["camera"]
        src = cam.get("source", 0)
        
        # Handle different source types
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        
        cap = cv2.VideoCapture(src)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cam.get("width",  640))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam.get("height", 480))
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   cam.get("buffer_size", 1))
        
        fps_target = cam.get("fps_target", 10)
        cap.set(cv2.CAP_PROP_FPS, fps_target)

        if not cap.isOpened():
            log.error("Cannot open source: %s", src)
            self._running = False
            return

        hist, prev = [], time.time()
        frame_count = 0
        
        while self._running:
            ok, frame = cap.read()
            if not ok:
                if isinstance(src, str) and not src.isdigit():
                    # Video file - loop
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.05)
                continue

            # Process every frame or throttle
            annotated, meta = self._process(frame, sv)

            now = time.time()
            frame_time = now - prev
            if frame_time > 0:
                hist.append(1.0 / frame_time)
            prev = now
            if len(hist) > 30:
                hist.pop(0)
            fps = sum(hist) / len(hist) if hist else 0

            meta["fps"]      = round(fps, 1)
            meta["uptime_s"] = int(now - self._start_time)
            meta["frame"]    = frame_count
            self.stats.update({
                "fps":          meta["fps"],
                "queens":       meta["queens"],
                "total_tracks": meta["total_tracks"],
                "alerts_saved": self.stats["alerts_saved"],
                "uptime_s":     meta["uptime_s"],
                "running":      True,
            })
            
            with self._lock:
                self._latest = (annotated, meta)
            
            frame_count += 1
            
            # Control frame rate
            if fps_target > 0:
                sleep_time = 1.0/fps_target - (time.time() - now)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        cap.release()
        log.info("Capture stopped")

    # ── inference ─────────────────────────────────────────────────────────────
    def _process(self, frame: np.ndarray, sv) -> tuple:
        m   = self.cfg["model"]
        
        # Run inference
        res = self.model.predict(
            frame,
            conf    = m.get("confidence", 0.40),
            iou     = m.get("iou", 0.50),
            imgsz   = m.get("imgsz", 416),
            device  = self.model_device,
            half    = m.get("half", False),
            verbose = False,
            classes = [0],
        )[0]

        boxes = res.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy      = boxes.xyxy.cpu().numpy()
            confs     = boxes.conf.cpu().numpy()
            class_ids = boxes.cls.cpu().numpy().astype(int)
        else:
            xyxy = np.empty((0, 4))
            confs = np.empty(0)
            class_ids = np.empty(0)

        dets = sv.Detections(
            xyxy       = xyxy.reshape(-1, 4) if len(xyxy) else np.empty((0, 4)),
            confidence = confs,
            class_id   = class_ids,
        )
        
        # Apply tracking if available
        if self._tracker is not None:
            try:
                tracked = self._tracker.update_with_detections(dets)
            except AttributeError:
                try:
                    tracked = self._tracker.update(dets)
                except AttributeError:
                    tracked = dets
        else:
            tracked = dets

        annotated = frame.copy()
        queens    = 0
        v         = self.cfg["visualization"]
        a         = self.cfg["alerts"]
        
        # Get tracker IDs if available
        has_tracker_id = hasattr(tracked, 'tracker_id') and tracked.tracker_id is not None

        for i in range(len(tracked)):
            x1, y1, x2, y2 = tracked.xyxy[i].astype(int)
            conf_v = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
            tid    = int(tracked.tracker_id[i]) if has_tracker_id else -1
            queens += 1

            if a.get("save", True):
                self._maybe_save(frame, (x1, y1, x2, y2), tid, conf_v)

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), QUEEN_BGR, v.get("bbox_thickness", 2))

            # Draw label
            parts = ["queen"]
            if v.get("show_track_id", True) and tid >= 0:
                parts.append(f"#{tid}")
            if v.get("show_confidence", True):
                parts.append(f"{conf_v:.0%}")
            txt = " ".join(parts)
            fs  = v.get("font_scale", 0.6)
            (tw, th), bl = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
            ty = max(y1 - 6, th + 4)
            cv2.rectangle(annotated, (x1, ty - th - bl - 2), (x1 + tw + 6, ty + 2), QUEEN_BGR, -1)
            cv2.putText(annotated, txt, (x1 + 3, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 0, 0), 1, cv2.LINE_AA)

        self._hud(annotated, queens, len(tracked))
        return annotated, {
            "queens": queens, 
            "total_tracks": len(tracked),
            "alerts_saved": self.stats["alerts_saved"],
        }

    # ── alert save ────────────────────────────────────────────────────────────
    def _maybe_save(self, frame, bbox, tid, conf):
        cooldown = self.cfg["alerts"].get("cooldown_seconds", 5)
        now      = time.time()
        if now - self._last_saved[tid] < cooldown:
            return
        self._last_saved[tid] = now
        pad = self.cfg["alerts"].get("crop_padding", 40)
        x1  = max(0, bbox[0] - pad)
        y1  = max(0, bbox[1] - pad)
        x2  = min(frame.shape[1], bbox[2] + pad)
        y2  = min(frame.shape[0], bbox[3] + pad)
        crop = frame[y1:y2, x1:x2]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        name = f"queen_id{tid}_{ts}_c{int(conf*100)}.jpg"
        cv2.imwrite(
            str(self._alerts_dir / name), crop,
            [cv2.IMWRITE_JPEG_QUALITY, self.cfg["alerts"].get("jpeg_quality", 92)]
        )
        self.stats["alerts_saved"] += 1
        log.info("Alert saved: %s", name)

    # ── HUD ───────────────────────────────────────────────────────────────────
    def _hud(self, frame, queens, tracks):
        ov = frame.copy()
        cv2.rectangle(ov, (8, 8), (230, 68), HUD_BG, -1)
        cv2.addWeighted(ov, 0.6, frame, 0.4, 0, frame)
        cv2.putText(frame, f"Queens : {queens}", (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, QUEEN_BGR, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Tracks : {tracks}", (16, 56),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA)