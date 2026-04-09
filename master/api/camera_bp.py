# ============================================================
#  R2-D2 Control System — Camera Stream Proxy
# ============================================================
"""
Camera blueprint — single-slot MJPEG proxy with last-connect-wins.

Endpoints:
  POST /camera/take       → claim exclusive stream access, returns token
  GET  /camera/stream?t=X → MJPEG proxy, stops if token is superseded
  GET  /camera/status     → { active_token: N } — for client polling
"""
import threading
import logging
import requests as _requests
from flask import Blueprint, Response, jsonify, request

camera_bp = Blueprint('camera', __name__)
log = logging.getLogger(__name__)

_lock         = threading.Lock()
_active_token = 0

MJPG_URL = 'http://127.0.0.1:8080/?action=stream'


@camera_bp.post('/camera/take')
def camera_take():
    """Claim the camera stream. Any previous holder will see their stream stop."""
    global _active_token
    with _lock:
        _active_token += 1
        token = _active_token
    log.debug("Camera claimed by %s — token %d", request.remote_addr, token)
    return jsonify({'token': token})


@camera_bp.get('/camera/stream')
def camera_stream():
    """
    MJPEG proxy. Requires a valid token from POST /camera/take.
    Stream ends automatically when another client claims the slot.
    """
    try:
        my_token = int(request.args.get('t', -1))
    except (ValueError, TypeError):
        my_token = -1

    if my_token != _active_token or my_token < 1:
        return jsonify({'error': 'No active token — call POST /camera/take first'}), 403

    def generate():
        try:
            resp = _requests.get(MJPG_URL, stream=True, timeout=5)
            for chunk in resp.iter_content(chunk_size=8192):
                if _active_token != my_token:
                    # Another client claimed the slot — stop this stream
                    break
                yield chunk
        except _requests.exceptions.ConnectionError:
            pass  # mjpg-streamer not running — stream ends silently
        except Exception as e:
            log.warning("Camera stream error: %s", e)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.get('/camera/status')
def camera_status():
    """Returns the current active token. Clients poll this to detect eviction."""
    return jsonify({'active_token': _active_token})
