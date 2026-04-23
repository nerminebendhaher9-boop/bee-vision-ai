# Local Setup for Bee Vision AI

## Current Status
- [x] Analyzed codebase and identified connection issues
- [x] Add Vite proxy in frontend/vite.config.ts
- [x] Replace hardcoded BACKEND_URL in QueenStream.tsx
- [x] Fix backend/server.js port clash and CORS default
- [x] Fix backend/server.py docstring
- [x] Test backend locally
- [x] Test frontend locally
- [x] Verify full local operation (no CORS errors)

## Run Instructions
```
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

## Notes
- The frontend now proxies API calls (`/infer`, `/stats`, `/alerts`, `/health`, `/test`) to the Python backend automatically. No CORS issues during development.
- `VITE_BACKEND_URL` env var can override the proxy if needed for production builds.
- The Node server (`backend/server.js`) now runs on port **7001** by default so it no longer collides with the Python backend on **7000**.
- If you accidentally start the Node server instead of the Python backend, the `/infer` stub will return a clear 503 message telling you to run `python app.py`.

