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
import os
import subprocess
import threading
import logging
import requests as _requests
from flask import Blueprint, Response, jsonify, request

camera_bp = Blueprint('camera', __name__)
log = logging.getLogger(__name__)

_lock         = threading.Lock()
_active_token = 0

MJPG_URL  = 'http://127.0.0.1:8080/?action=stream'
_ENV_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'camera.env')

_VALID_RESOLUTIONS = {'640x480', '1280x720', '1920x1080'}
_VALID_FPS         = {15, 30}
_VALID_QUALITY     = range(10, 101)


def _read_cam_env() -> dict:
    cfg = {'resolution': '640x480', 'fps': 30, 'quality': 80}
    try:
        with open(_ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if '=' not in line or line.startswith('#'):
                    continue
                k, v = line.split('=', 1)
                if k == 'CAMERA_RESOLUTION':
                    cfg['resolution'] = v
                elif k == 'CAMERA_FPS':
                    cfg['fps'] = int(v)
                elif k == 'CAMERA_QUALITY':
                    cfg['quality'] = int(v)
    except FileNotFoundError:
        pass
    return cfg


def _write_cam_env(resolution: str, fps: int, quality: int) -> None:
    os.makedirs(os.path.dirname(_ENV_PATH), exist_ok=True)
    with open(_ENV_PATH, 'w') as f:
        f.write(f'CAMERA_RESOLUTION={resolution}\n')
        f.write(f'CAMERA_FPS={fps}\n')
        f.write(f'CAMERA_QUALITY={quality}\n')


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
    Forwards the upstream Content-Type so the browser gets the correct boundary.
    """
    try:
        my_token = int(request.args.get('t', -1))
    except (ValueError, TypeError):
        my_token = -1

    if my_token != _active_token or my_token < 1:
        return jsonify({'error': 'No active token — call POST /camera/take first'}), 403

    try:
        upstream = _requests.get(MJPG_URL, stream=True, timeout=5)
        content_type = upstream.headers.get(
            'Content-Type',
            'multipart/x-mixed-replace; boundary=boundarydonotcross'
        )
    except _requests.exceptions.ConnectionError:
        log.warning("Camera not reachable at %s", MJPG_URL)
        return jsonify({'error': 'Camera not available'}), 503
    except Exception as e:
        log.warning("Camera connect error: %s", e)
        return jsonify({'error': 'Camera error'}), 503

    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=8192):
                if _active_token != my_token:
                    # Another client claimed the slot — stop this stream
                    break
                yield chunk
        except Exception as e:
            log.warning("Camera stream error: %s", e)

    return Response(generate(), mimetype=content_type)


@camera_bp.get('/camera/status')
def camera_status():
    """Returns the current active token. Clients poll this to detect eviction."""
    return jsonify({'active_token': _active_token})


@camera_bp.post('/camera/release')
def camera_release():
    """Release the stream — resets active token to 0 so /status reports camera_active=false."""
    global _active_token
    with _lock:
        _active_token = 0
    return '', 204


@camera_bp.get('/camera/config')
def camera_config_get():
    """Returns current camera resolution/fps/quality settings."""
    return jsonify(_read_cam_env())


@camera_bp.post('/camera/config')
def camera_config_set():
    """
    Saves camera settings and restarts r2d2-camera.service.
    Body: { resolution: '1280x720', fps: 30, quality: 80 }
    """
    data       = request.get_json(silent=True) or {}
    resolution = data.get('resolution', '640x480')
    fps        = int(data.get('fps', 30))
    quality    = int(data.get('quality', 80))

    if resolution not in _VALID_RESOLUTIONS:
        return jsonify({'error': f'Invalid resolution — valid: {sorted(_VALID_RESOLUTIONS)}'}), 400
    if fps not in _VALID_FPS:
        return jsonify({'error': f'Invalid fps — valid: {sorted(_VALID_FPS)}'}), 400
    if quality not in _VALID_QUALITY:
        return jsonify({'error': 'Quality must be 10–100'}), 400

    _write_cam_env(resolution, fps, quality)
    log.info("Camera config: %s @ %dfps q%d — restarting service", resolution, fps, quality)

    def _restart():
        subprocess.run(['sudo', 'systemctl', 'restart', 'r2d2-camera.service'], check=False)

    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({'status': 'ok', 'resolution': resolution, 'fps': fps, 'quality': quality})
