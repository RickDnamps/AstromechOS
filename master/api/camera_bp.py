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
import time
import logging
import requests as _requests
from flask import Blueprint, Response, jsonify, request
from master.api._admin_auth import require_admin

camera_bp = Blueprint('camera', __name__)
log = logging.getLogger(__name__)

_lock         = threading.Lock()
_active_token = 0
# Audit finding Camera M-2 2026-05-15: bounded concurrent stream
# count. 8 covers any realistic 2-3 tablet + spare reconnect scenario.
_MAX_ACTIVE_STREAMS = 8
_active_streams = 0
_streams_lock   = threading.Lock()

_ENV_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'camera.env')


def _mjpg_url() -> str:
    """Build the mjpg_streamer proxy URL from local.cfg [camera] port,
    falling back to 8080. Audit finding Camera H-4 2026-05-15: was
    hardcoded — violated 'never hardcode installation values'. Reads
    on every call (cheap) so changes take effect without master
    reboot."""
    try:
        import configparser as _cp
        from shared.paths import LOCAL_CFG, MAIN_CFG
        cfg = _cp.ConfigParser()
        cfg.read([MAIN_CFG, LOCAL_CFG])
        port = cfg.getint('camera', 'mjpg_port', fallback=8080)
    except Exception:
        port = 8080
    return f'http://127.0.0.1:{port}/?action=stream'


# Backward compat for any external caller importing the constant.
MJPG_URL = _mjpg_url()

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
    # Audit finding Camera M-5 2026-05-15: chmod the TMP file before
    # os.replace, not the destination after. Previously left a tiny
    # window where the dest file was world-readable (umask=0o022 →
    # 0o644 at create time). Now the replaced file inherits 0o600.
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, _ENV_PATH)
    try:
        os.chmod(_ENV_PATH, 0o600)   # belt + braces
    except OSError:
        pass


_TAKE_RATE_LIMIT_PER_IP: dict = {}   # ip → (count, window_start)
_TAKE_LIMIT_LOCK = threading.Lock()
_TAKE_MAX_PER_WINDOW = 10
_TAKE_WINDOW_SECONDS = 10.0


@camera_bp.post('/camera/take')
def camera_take():
    """Claim the camera stream. Any previous holder will see their stream stop.

    Audit finding Camera H-3 2026-05-15: was unauthenticated AND
    unrate-limited — any LAN client could spam /take continually,
    evicting the operator's view every chunk. Now per-IP rate-limit:
    max 10 takes per 10 seconds. Returns 429 over that. Admin auth
    not required so multiple legit tablets can hot-swap quickly."""
    ip = request.remote_addr or 'unknown'
    now = time.monotonic()
    with _TAKE_LIMIT_LOCK:
        bucket = _TAKE_RATE_LIMIT_PER_IP.get(ip, (0, now))
        count, window_start = bucket
        if now - window_start > _TAKE_WINDOW_SECONDS:
            count, window_start = 0, now
        count += 1
        _TAKE_RATE_LIMIT_PER_IP[ip] = (count, window_start)
    if count > _TAKE_MAX_PER_WINDOW:
        log.warning("camera_take rate-limited: %s (%d in window)", ip, count)
        return jsonify({'error': 'too many takes', 'retry_after_s': int(_TAKE_WINDOW_SECONDS)}), 429
    global _active_token
    with _lock:
        _active_token += 1
        token = _active_token
    log.debug("Camera claimed by %s — token %d", ip, token)
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

    # Audit finding Camera M-2 2026-05-15: cap concurrent generate()
    # instances. Token-eviction stops the previous viewer's stream on
    # the next mjpg_streamer chunk (~33ms at 30fps), but during rapid
    # reconnects N upstreams can briefly coexist. Cap protects against
    # rogue clients holding sockets open.
    global _active_streams
    if _active_streams >= _MAX_ACTIVE_STREAMS:
        log.warning("Camera stream cap reached (%d)", _active_streams)
        return jsonify({'error': 'too many active streams'}), 503

    try:
        upstream = _requests.get(_mjpg_url(), stream=True, timeout=2)
        content_type = upstream.headers.get(
            'Content-Type',
            'multipart/x-mixed-replace; boundary=boundarydonotcross'
        )
    except _requests.exceptions.ConnectionError:
        log.warning("Camera not reachable at %s", _mjpg_url())
        return jsonify({'error': 'Camera not available'}), 503
    except _requests.exceptions.RequestException as e:
        # Audit finding Camera L-5 2026-05-15: narrowed from bare
        # Exception to RequestException — actual transport errors get
        # caught here, but a programming bug (e.g. AttributeError)
        # surfaces in journalctl instead of being swallowed.
        log.warning("Camera connect error: %s", e)
        return jsonify({'error': 'Camera error'}), 503

    # Increment active stream count under the dedicated lock.
    # (global _active_streams already declared above for the cap check.)
    with _streams_lock:
        _active_streams += 1

    def generate():
        global _active_streams
        try:
            for chunk in upstream.iter_content(chunk_size=8192):
                if _active_token != my_token:
                    break
                yield chunk
        except (_requests.exceptions.RequestException, OSError) as e:
            # Audit finding Camera L-5 (sibling): narrow exception in
            # the streaming loop too. Bare Exception used to swallow
            # all errors silently; now non-transport bugs surface.
            log.warning("Camera stream error: %s", e)
        finally:
            try:
                upstream.close()
            except OSError:
                pass
            with _streams_lock:
                _active_streams -= 1

    return Response(generate(), mimetype=content_type)


@camera_bp.get('/camera/status')
def camera_status():
    """Returns the current active token. Clients poll this to detect eviction."""
    with _lock:
        return jsonify({'active_token': _active_token})


@camera_bp.post('/camera/release')
def camera_release():
    """Release the stream — resets active token to 0 so /status reports camera_active=false.

    Audit finding Camera H-2 2026-05-15: was unauthenticated — any
    LAN guest could POST /camera/release to evict the legitimate
    viewer. Now requires the caller to present their own token
    (the one /camera/take returned) OR be authenticated as admin.
    Without a matching token, refuses with 401."""
    global _active_token   # need explicit global because we assign below
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    presented = body.get('token')
    admin_pw = request.headers.get('X-Admin-Pw', '')
    is_admin = False
    if admin_pw:
        try:
            from master.api._admin_auth import _get_admin_password
            import hmac
            is_admin = hmac.compare_digest(admin_pw.encode(), _get_admin_password().encode())
        except Exception:
            is_admin = False
    with _lock:
        token_match = isinstance(presented, int) and presented == _active_token and _active_token > 0
        if not (is_admin or token_match):
            return jsonify({'error': 'token mismatch'}), 401
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
