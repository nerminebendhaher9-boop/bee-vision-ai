# Bee Vision AI — Fix Render Deployment (Eventlet → Gevent)

## Plan Progress
- [x] Step 1: Update `backend/requirements.txt` — replace eventlet with gevent
- [x] Step 2: Update `backend/app.py` — change SocketIO async_mode to gevent
- [x] Step 3: Update `backend/wsgi.py` — replace eventlet monkey patch with gevent
- [x] Step 4: Update `backend/server.py` — update comments for gevent consistency
- [x] Step 5: Update `render.yaml` — change gunicorn worker from eventlet to gevent
- [ ] Step 6: Test locally and verify

## Issue
Render runs Python 3.14.3. `eventlet==0.36.0` is incompatible with Python 3.14 due to changed `_thread` internal APIs. The `PYTHON_VERSION: 3.12.11` env var is ignored by Render's native Python runtime.

## Solution
Switch from `eventlet` to `gevent` (>=24.11.1), which supports Python 3.14.

## Changes Made
1. **`backend/requirements.txt`**: Replaced `eventlet==0.36.0` with `gevent>=24.11.1` and `greenlet>=3.1.1`
2. **`backend/app.py`**: Changed `async_mode='eventlet'` → `async_mode='gevent'` for Render
3. **`backend/wsgi.py`**: Replaced `eventlet.monkey_patch()` with `gevent.monkey.patch_all()`, updated banner + docstring
4. **`backend/server.py`**: Updated banner text to reflect Gevent
5. **`render.yaml`**: Changed gunicorn start command from `-k eventlet` to `-k gevent`

## Next Steps
1. Install new dependencies locally:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Test the backend locally with your Python 3.12
3. Push to GitHub and redeploy on Render

