"""
train.py  —  BEE AI PRO
Local YOLOv8m training — mirrors your Colab notebook exactly.
100% offline after first weight download.

Usage
-----
  python train.py                          # default config
  python train.py --device cpu --batch 4   # CPU mode
  python train.py --resume                 # resume last run
  python train.py --validate               # eval best.pt only
"""
from __future__ import annotations
import argparse, logging, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.train")

BANNER = """
╔══════════════════════════════════════════════════════╗
║   🐝  BEE AI PRO — LOCAL TRAINING                   ║
║       YOLOv8m  |  queen class only  |  No Cloud     ║
╚══════════════════════════════════════════════════════╝"""


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs",   type=int,   default=100)
    p.add_argument("--batch",    type=int,   default=16)
    p.add_argument("--imgsz",    type=int,   default=640)
    p.add_argument("--device",   type=str,   default="")
    p.add_argument("--patience", type=int,   default=15)
    p.add_argument("--workers",  type=int,   default=4)
    p.add_argument("--conf",     type=float, default=0.40)
    p.add_argument("--weights",  type=str,   default="yolov8m.pt")
    p.add_argument("--resume",   action="store_true")
    p.add_argument("--validate", action="store_true")
    return p.parse_args()


def resolve_device(d):
    if d: return d
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def main():
    print(BANNER)
    a = args()
    device    = resolve_device(a.device)
    data_yaml = ROOT / "dataset" / "data.yaml"
    out_dir   = ROOT / "runs" / "train"
    name      = "queen_detector"
    dst_pt    = ROOT / "models" / "weights" / "best.pt"

    log.info("Device   : %s", device)
    log.info("Epochs   : %d  Batch: %d  ImgSz: %d", a.epochs, a.batch, a.imgsz)
    log.info("Data     : %s", data_yaml)

    if not data_yaml.exists():
        log.error("data.yaml not found — prepare dataset first (see README)")
        sys.exit(1)

    from ultralytics import YOLO

    if a.validate:
        if not dst_pt.exists():
            log.error("No weights at %s — train first", dst_pt)
            sys.exit(1)
        log.info("Running validation only…")
        m = YOLO(str(dst_pt))
        metrics = m.val(data=str(data_yaml), imgsz=a.imgsz, conf=a.conf, device=device, plots=True)
        log.info("mAP@50    : %.4f", metrics.box.map50)
        log.info("mAP@50-95 : %.4f", metrics.box.map)
        return

    # ── base weights ──────────────────────────────────────────────────────────
    if a.resume:
        last = out_dir / name / "weights" / "last.pt"
        if not last.exists():
            log.error("No checkpoint at %s", last); sys.exit(1)
        base = str(last)
    else:
        base = str(dst_pt) if dst_pt.exists() else a.weights

    log.info("Base weights: %s", base)

    model = YOLO(base)
    results = model.train(
        data       = str(data_yaml),
        epochs     = a.epochs,
        batch      = a.batch,
        imgsz      = a.imgsz,
        patience   = a.patience,
        device     = device,
        workers    = a.workers,
        project    = str(out_dir),
        name       = name,
        optimizer  = "AdamW",
        lr0        = 0.001,
        mosaic     = 1.0,
        augment    = True,
        cache      = True,
        resume     = a.resume,
        plots      = True,
        save       = True,
        save_period= 10,
        classes    = [0],
        verbose    = True,
    )

    # ── copy best weights to standard location ────────────────────────────────
    src = Path(results.save_dir) / "weights" / "best.pt"
    dst_pt.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst_pt)
        log.info("✅ best.pt saved → %s", dst_pt)
    else:
        log.warning("best.pt not found at %s", src)

    # ── final validation ──────────────────────────────────────────────────────
    log.info("Final validation…")
    val_m   = YOLO(str(dst_pt))
    metrics = val_m.val(data=str(data_yaml), imgsz=a.imgsz, conf=a.conf, device=device, plots=True)
    map50   = metrics.box.map50

    if map50 >= 0.80:
        print(f"\n  🎯  TARGET HIT — mAP@50 = {map50:.4f}  ✅\n")
    else:
        print(f"\n  ⚠   mAP@50 = {map50:.4f} — check TRAINING_GUIDE.md\n")


if __name__ == "__main__":
    main()
