"""
server.py — Pour Gunicorn sur Render
Adaptation pour fonctionner avec l'existant
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Ajoute le chemin racine
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bee.wsgi")

print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   🐝  BEE AI PRO  —  Queen Detection System         ║
║       Mode Gunicorn pour Render                      ║
║                                                      ║
╚══════════════════════════════════════════════════════╝""")

# Importe l'application Flask depuis app.py
from app import app, socketio, start_broadcast, get_tracker

log.info("Initialisation du tracker...")
try:
    get_tracker()
    log.info("✅ Tracker initialisé")
except Exception as e:
    log.error("Erreur tracker: %s", e)
    # Continue quand même, peut-être que ça marchera au runtime

# Démarre le broadcast
try:
    start_broadcast()
    log.info("✅ Broadcast démarré")
except Exception as e:
    log.warning("Broadcast non démarré: %s", e)

# Pour Gunicorn - l'application WSGI
application = app

log.info("WSGI prête pour Gunicorn")