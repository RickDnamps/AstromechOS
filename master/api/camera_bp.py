# ============================================================
#  AstromechOS — Camera Stream Proxy
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
from master.api._admin_auth import require_admin

camera_bp = Blueprint('camera', __name__)
log = logging.getLogger(__name__)

_lock         = threading.Lock()
_active_token = 0

MJPG_URL  = 'http://127.0.0.1:8080/?action=stream'
_ENV_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'camera.env')

_VALID_RESOLUTIONS = {'640x480', '1280x720', '1920x1080'}
_VALID_FPS         = {15, 30}
_VALID_QUALITY     = range(10, 101)

# B-208 (remaining tabs audit 2026-05-15): debounce timer for the
# astromech-camera.service restart. Rapid /camera/config POSTs (drag
# the quality slider) coalesce into one restart after _RESTART_DEBOUNCE
# seconds of idle. _restart_lock protects the timer reference.
_RESTART_DEBOUNCE = 2.0
_restart_timer: threading.Timer | None = None
_restart_lock   = threading.Lock()


def _schedule_camera_restart() -> None:
    """Coalesce multiple restart triggers within _RESTART_DEBOUNCE
    seconds into a single systemctl restart. Each call resets the
    countdown, so the operator's last edit wins and mjpg_streamer
    isn't repeatedly killed mid-init."""
    global _restart_timer

    def _do_restart():
        try:
            subprocess.run(['sudo', 'systemctl', 'restart',
                            'astromech-camera.service'], check=False)
            log.info("Camera service restart issued")
        except OSError as e:
            log.warning("Camera service restart failed: %s", e)

    with _restart_lock:
        if _restart_timer is not None and _restart_timer.is_alive():
            _restart_timer.cancel()
        _restart_timer = threading.Timer(_RESTART_DEBOUNCE, _do_restart)
        _restart_timer.daemon = True
        _restart_timer.start()


def _read_cam_env() -> dict:
    """Read camera.env. B-210 (remaining tabs audit 2026-05-15):
    tolerate malformed int values per-line instead of bubbling a
    ValueError up to /camera/config GET (which would 500). Keep the
    default for any field that fails parsing."""
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
                    try:
                        cfg['fps'] = int(v)
                    except ValueError:
                        log.warning("camera.env: invalid CAMERA_FPS=%r (using default)", v)
                elif k == 'CAMERA_QUALITY':
                    try:
                        cfg['quality'] = int(v)
                    except ValueError:
                        log.warning("camera.env: invalid CAMERA_QUALITY=%r (using default)", v)
    except FileNotFoundError:
        pass
    except OSError as e:
        log.warning("camera.env unreadable: %s", e)
    return cfg


def _write_cam_env(resolution: str, fps: int, quality: int) -> None:
    """B-203 (remaining tabs audit 2026-05-15): atomic tmp+replace.
    Was open(w) which truncated then wrote — a crash mid-write or a
    concurrent read by `scripts/camera-start.sh` (which sources this
    file at service start) would have seen an empty/partial file →
    fallback defaults kick in silently. Pattern matches settings_bp
    write_cfg_atomic + chmod 0600 (the env may eventually hold
    sensitive camera tokens)."""
    os.makedirs(os.path.dirname(_ENV_PATH), exist_ok=True)
    tmp = _ENV_PATH + '.tmp'
    with open(tmp, 'w') as f:
        f.write(f'CAMERA_RESOLUTION={resolution}\n')
        f.write(f'CAMERA_FPS={fps}\n')
        f.write(f'CAMERA_QUALITY={quality}\n')
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, _ENV_PATH)
    try:
        # Audit finding M-3 2026-05-15: camera-start.sh runs under
        # User=artoo (same as the master service), so 0o600 still
        # works — drops world+group read so future camera tokens
        # added to this file are owner-only. Matches write_cfg_atomic.
        os.chmod(_ENV_PATH, 0o600)
    except OSError:
        pass


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
        # B-265 (remaining tabs audit 2026-05-15): drop timeout 5s→2s.
        # MJPG_URL is localhost — a 2s timeout still covers a healthy
        # mjpg_streamer cold-start. Going beyond that meant a wedged
        # service tied up Flask worker threads for 5s × N concurrent
        # clients during reconnects.
        upstream = _requests.get(MJPG_URL, stream=True, timeout=2)
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
        # B-209 (remaining tabs audit 2026-05-15): always close the
        # upstream connection on exit (success, eviction, or exception).
        # Previously the upstream `requests.Response` leaked when the
        # client disconnected mid-stream — `iter_content` would raise,
        # the bare-except swallowed it, but the underlying TCP socket
        # to mjpg_streamer stayed open until GC. Heavy churn (multiple
        # tablets reconnecting) exhausted the local-port pool over time.
        try:
            for chunk in upstream.iter_content(chunk_size=8192):
                if _active_token != my_token:
                    # Another client claimed the slot — stop this stream
                    break
                yield chunk
        except Exception as e:
            log.warning("Camera stream error: %s", e)
        finally:
            try:
                upstream.close()
            except Exception:
                pass

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
@require_admin
def camera_config_set():
    """
    Saves camera settings and restarts astromech-camera.service.
    Body: { resolution: '1280x720', fps: 30, quality: 80 }
    """
    data       = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    resolution = data.get('resolution', '640x480')
    # B-231 / B-232 (remaining tabs audit 2026-05-15): defensive int
    # parsing — a non-numeric `fps` or `quality` body field used to
    # propagate ValueError → 500. Now: clear 400 with the offending
    # field name.
    try:
        fps     = int(data.get('fps', 30))
        quality = int(data.get('quality', 80))
    except (TypeError, ValueError):
        return jsonify({'error': 'fps and quality must be integers'}), 400

    if resolution not in _VALID_RESOLUTIONS:
        return jsonify({'error': f'Invalid resolution — valid: {sorted(_VALID_RESOLUTIONS)}'}), 400
    if fps not in _VALID_FPS:
        return jsonify({'error': f'Invalid fps — valid: {sorted(_VALID_FPS)}'}), 400
    if quality not in _VALID_QUALITY:
        return jsonify({'error': 'Quality must be 10–100'}), 400

    _write_cam_env(resolution, fps, quality)
    log.info("Camera config: %s @ %dfps q%d — restarting service", resolution, fps, quality)

    # B-208 (remaining tabs audit 2026-05-15): serialize restarts.
    # Rapid /camera/config POSTs (operator dragging the quality
    # slider) would otherwise spawn N restart commands → mjpg_streamer
    # killed mid-init repeatedly, camera goes dark. Single-flight slot
    # protects the systemctl call; subsequent restarts during the 3s
    # window collapse to one final restart by debouncing the trigger
    # via a coalescing timer.
    _schedule_camera_restart()
    return jsonify({'status': 'ok', 'resolution': resolution, 'fps': fps, 'quality': quality})
