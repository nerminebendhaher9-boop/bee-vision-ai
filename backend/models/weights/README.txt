Place your trained weights here as: best.pt

From your Google Colab notebook:
  1. Download queen_detector_model.pt from Google Drive
  2. Rename it to best.pt
  3. Copy to this folder: backend/models/weights/best.pt

Or train locally:
  cd backend
  python train.py --device cpu --batch 4
