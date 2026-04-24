# Bee Vision AI — Setup & Deployment

## Current Status
- [x] Analyzed codebase and identified connection issues
- [x] Add Vite proxy in frontend/vite.config.ts
- [x] Replace hardcoded BACKEND_URL in QueenStream.tsx
- [x] Fix backend/server.js port clash and CORS default
- [x] Fix backend/server.py docstring
- [x] Test backend locally
- [x] Test frontend locally
- [x] Verify full local operation (no CORS errors)
- [x] Fix Render deployment configuration
- [x] Update CORS for production frontend URL
- [x] Fix SocketIO async_mode for gunicorn+eventlet
- [x] Fix wsgi.py eventlet monkey patch order
- [x] Add render.yaml for Render Blueprint deployment

## Local Development
```bash
# Terminal 1 - Backend (Python Flask)
cd backend
pip install -r requirements.txt
python app.py
# Runs on http://localhost:7000

# Terminal 2 - Frontend (Vite+React)
cd frontend
npm install
npm run dev
# Runs on http://localhost:8080
```

## Render Deployment

### Services (configured in `render.yaml`)
| Service | Type | URL | Plan |
|---------|------|-----|------|
| bee-vision-ai-b | Web (Python) | https://bee-vision-ai-b.onrender.com | Free |
| bee-vision-ai | Static | https://bee-vision-ai.onrender.com | Free |

### Deploy Steps
1. Push code to GitHub
2. In Render Dashboard → **Blueprints** → **New Blueprint Instance**
3. Select this repo and the `render.yaml` file
4. Render will create both services automatically

### Manual Deploy (if not using Blueprint)
**Backend:**
- Build Command: `pip install -r backend/requirements.txt`
- Start Command: `cd backend && gunicorn wsgi:application -k eventlet -w 1 --bind 0.0.0.0:$PORT`
- Add Environment Variable: `RENDER=true`

**Frontend:**
- Build Command: `cd frontend && npm install && npm run build`
- Publish Directory: `./frontend/dist`
- Add Environment Variable: `VITE_BACKEND_URL=https://bee-vision-ai-b.onrender.com`

## Notes
- **Local dev**: Frontend proxies API calls automatically via Vite dev server
- **Production**: Frontend uses `https://bee-vision-ai-b.onrender.com` as backend
- The Node server (`backend/server.js`) runs on port **7001** locally to avoid collision
- Camera quality upgraded to 1920×1080 ideal resolution with 92% JPEG quality

