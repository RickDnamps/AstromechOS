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
# B3 fix 2026-05-16: tighten to the slider's step=5 grid. Was range(10,101)
# which accepted any int 10..100 → curl POST with quality=73 stored 73,
# but UI slider only snaps to multiples of 5 → next page load showed 75
# while actual stream ran at 73 (UI lied).
_VALID_QUALITY     = set(range(10, 101, 5))   # {10, 15, 20, ..., 100}

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
            # E6 fix 2026-05-16: explicit timeout — was unbounded, so a
            # hung systemd (rare but possible on sd-card thrash) parked
            # the timer thread forever. 10s is generous for restart.
            subprocess.run(['sudo', 'systemctl', 'restart',
                            'astromech-camera.service'],
                           check=False, timeout=10)
            log.info("Camera service restart issued")
        except subprocess.TimeoutExpired:
            log.warning("Camera service restart timed out (>10s)")
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
    # B9 fix 2026-05-16: validate resolution before returning. If
    # camera.env was hand-edited to an unsupported value, the <select>
    # would silently snap to first option (640x480) → UI lied while
    # actual stream stayed broken.
    if cfg['resolution'] not in _VALID_RESOLUTIONS:
        log.warning("camera.env: invalid CAMERA_RESOLUTION=%r (using default)", cfg['resolution'])
        cfg['resolution'] = '640x480'
    if cfg['fps'] not in _VALID_FPS:
        cfg['fps'] = 30
    if cfg['quality'] not in _VALID_QUALITY:
        # Snap to nearest grid step instead of resetting (preserve intent)
        cfg['quality'] = max(_VALID_QUALITY, key=lambda q: -abs(q - cfg['quality'])) if cfg['quality'] >= 10 else 80
    return cfg


def _write_cam_env(resolution: str, fps: int, quality: int) -> bool:
    """B-203 atomic tmp+replace. Returns True if file actually changed.
    B5 fix 2026-05-16: skip rotate+write if content is identical to
    current file. Was: every POST /camera/config rotated .bak even
    when operator dragged the slider with no net change → 30-step
    quality drag filled all 3 .bak generations with near-identical
    values → 'before any of this' state irrecoverable.
    E5 fix: also skips the os.makedirs syscall + fsync churn.
    """
    new_content = (
        f'CAMERA_RESOLUTION={resolution}\n'
        f'CAMERA_FPS={fps}\n'
        f'CAMERA_QUALITY={quality}\n'
    )
    # Skip-if-unchanged short-circuit
    try:
        with open(_ENV_PATH, 'r') as _f:
            if _f.read() == new_content:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(_ENV_PATH), exist_ok=True)
    from master.config.config_loader import rotate_backup as _rotate
    _rotate(_ENV_PATH)
    tmp = _ENV_PATH + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_content)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, _ENV_PATH)
    try:
        os.chmod(_ENV_PATH, 0o600)
    except OSError:
        pass
    return True


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
        # E2 fix 2026-05-16: prune stale entries when dict grows. Was
        # unbounded — long-running Master with DHCP churn accumulated
        # thousands of dead entries + a hostile LAN device cycling
        # MACs could exhaust memory.
        if len(_TAKE_RATE_LIMIT_PER_IP) > 256:
            cutoff = now - 2 * _TAKE_WINDOW_SECONDS
            for stale_ip in [ip2 for ip2, (_, ws) in _TAKE_RATE_LIMIT_PER_IP.items() if ws < cutoff]:
                _TAKE_RATE_LIMIT_PER_IP.pop(stale_ip, None)
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

    # E1 fix 2026-05-16: snapshot _active_token under _lock — was read
    # without the lock, racing /camera/take writer. Rare false-403
    # ("No active token") when client polled /take and immediately
    # called /stream with the just-issued token from another thread.
    with _lock:
        active_now = _active_token
    if my_token != active_now or my_token < 1:
        return jsonify({'error': 'No active token — call POST /camera/take first'}), 403

    # P1 fix 2026-05-16: cap check + increment in ONE critical section.
    # Was: read-without-lock cap check, then increment under lock →
    # two concurrent /camera/stream both saw _active_streams=7, both
    # passed cap, both incremented to 9 (overshoot). Now atomic.
    global _active_streams
    with _streams_lock:
        if _active_streams >= _MAX_ACTIVE_STREAMS:
            log.warning("Camera stream cap reached (%d)", _active_streams)
            return jsonify({'error': 'too many active streams'}), 503
        _active_streams += 1
        slot_acquired = True

    try:
        upstream = _requests.get(_mjpg_url(), stream=True, timeout=2)
        content_type = upstream.headers.get(
            'Content-Type',
            'multipart/x-mixed-replace; boundary=boundarydonotcross'
        )
    except _requests.exceptions.ConnectionError:
        # P1 fix: release slot if upstream connect fails (was leaked
        # since we incremented before the try/except).
        with _streams_lock:
            _active_streams -= 1
        log.warning("Camera not reachable at %s", _mjpg_url())
        return jsonify({'error': 'Camera not available'}), 503
    except _requests.exceptions.RequestException as e:
        with _streams_lock:
            _active_streams -= 1
        log.warning("Camera connect error: %s", e)
        return jsonify({'error': 'Camera error'}), 503

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


@camera_bp.get('/camera/snapshot')
def camera_snapshot():
    """W6 fix 2026-05-16: proxy a single MJPEG frame from mjpg_streamer's
    ?action=snapshot endpoint. Returns image/jpeg with attachment
    header. Token-free (LAN-open like /camera/take is) so operator
    can quick-share without dance. Rate-limited per IP via same
    bucket as /camera/take."""
    ip = request.remote_addr or 'unknown'
    now = time.monotonic()
    with _TAKE_LIMIT_LOCK:
        bucket = _TAKE_RATE_LIMIT_PER_IP.get(f'snap:{ip}', (0, now))
        count, window_start = bucket
        if now - window_start > _TAKE_WINDOW_SECONDS:
            count, window_start = 0, now
        count += 1
        _TAKE_RATE_LIMIT_PER_IP[f'snap:{ip}'] = (count, window_start)
    if count > _TAKE_MAX_PER_WINDOW:
        return jsonify({'error': 'snapshot rate limit', 'retry_after_s': int(_TAKE_WINDOW_SECONDS)}), 429
    # mjpg_streamer exposes ?action=snapshot — single JPEG
    snap_url = _mjpg_url().replace('?action=stream', '?action=snapshot')
    try:
        r = _requests.get(snap_url, timeout=3)
        if r.status_code != 200:
            return jsonify({'error': f'camera returned HTTP {r.status_code}'}), 503
    except _requests.exceptions.RequestException as e:
        log.warning("snapshot fetch failed: %s", e)
        return jsonify({'error': 'Camera not available'}), 503
    import time as _t2
    fname = f'r2d2-{_t2.strftime("%Y%m%d-%H%M%S", _t2.localtime())}.jpg'
    return Response(r.content, mimetype='image/jpeg',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


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
