# ============================================================
#  AstromechOS — Backup / Restore + server-side custom themes
# ============================================================
"""Blueprint: server-side custom themes (B.0) + full Backup/Restore (B.1/B.2).

Themes were browser-localStorage only; persisting them here makes them
multi-device + included in the backup.
"""
import json
import logging
import os
import posixpath
import shutil
import tempfile
import threading
import time
import zipfile

from flask import Blueprint, request, jsonify, send_file, after_this_request
from master.api._admin_auth import require_admin, get_json_object
from master.api.backup_core import (validate_theme, BACKUP_FILESET, build_manifest,
                                     is_safe_member, validate_manifest, merge_local_cfg)
from shared.paths import SLAVE_SOUNDS as _SLAVE_SOUNDS

log = logging.getLogger(__name__)
backup_bp = Blueprint('backup', __name__)

_REPO = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Remote slave repo root derived from the (POSIX) remote sounds path — no new
# hardcoded install value (reuses shared.paths.SLAVE_SOUNDS).
_SLAVE_REPO = posixpath.dirname(posixpath.dirname(_SLAVE_SOUNDS))
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
_THEMES_FILE = os.path.join(_CONFIG_DIR, 'custom_themes.json')
_themes_lock = threading.Lock()
_CUSTOM_THEMES_MAX = 16


def _read_themes() -> list:
    try:
        with open(_THEMES_FILE, encoding='utf-8') as f:
            d = json.load(f)
        return d.get('themes', []) if isinstance(d, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_themes(themes: list) -> None:
    """Atomic write: tmp + fsync + os.replace (same pattern as the sounds index)."""
    tmp = _THEMES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'themes': themes}, f, indent=2, ensure_ascii=False)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, _THEMES_FILE)


@backup_bp.get('/themes/custom')
def themes_list():
    """List custom themes (LAN-open read, like other read endpoints)."""
    return jsonify({'themes': _read_themes()})


@backup_bp.post('/themes/custom')
@require_admin
def themes_save():
    """Add or update one custom theme (validated server-side)."""
    body = get_json_object()
    theme = body.get('theme') if isinstance(body, dict) else None
    if not validate_theme(theme):
        return jsonify({'ok': False, 'error': 'invalid theme'}), 400
    with _themes_lock:
        themes = [t for t in _read_themes() if t.get('id') != theme['id']]
        if len(themes) >= _CUSTOM_THEMES_MAX:
            return jsonify({'ok': False, 'error': f'max {_CUSTOM_THEMES_MAX} themes'}), 400
        themes.append(theme)
        _write_themes(themes)
    return jsonify({'ok': True})


@backup_bp.route('/themes/custom/<tid>', methods=['DELETE'])
@require_admin
def themes_delete(tid):
    """Delete one custom theme by id."""
    with _themes_lock:
        themes = [t for t in _read_themes() if t.get('id') != tid]
        _write_themes(themes)
    return jsonify({'ok': True})


# ── Backup (B.1): async job + status polling + download ──────────────────────
_backup_lock = threading.Lock()
_backup_job = {'running': False, 'pct': 0, 'phase': '', 'done': False,
               'error': None, 'path': None}


def _local_version():
    try:
        with open(os.path.join(_REPO, 'VERSION'), encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return 'unknown'


def _robot_name():
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read([os.path.join(_REPO, 'master/config/main.cfg'),
              os.path.join(_REPO, 'master/config/local.cfg')])
    return cfg.get('robot', 'name', fallback='AstromechOS')


def _run_backup():
    """Assemble the .bck in a temp dir, tracking pct/phase. Master files copied
    locally; slave files pulled via SFTP (the long phase = the ~69 MB of sounds)."""
    job = _backup_job
    stage = tempfile.mkdtemp(prefix='astrobk_')
    try:
        files = []
        job.update(phase='Collecting master config + choreos', pct=5)
        for rel in BACKUP_FILESET['master']:
            src = os.path.join(_REPO, rel)
            if rel.endswith('/'):
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(stage, rel), dirs_exist_ok=True)
                    files += [rel + f for f in os.listdir(src)
                              if os.path.isfile(os.path.join(src, f))]
            elif os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
                shutil.copy2(src, os.path.join(stage, rel))
                files.append(rel)

        job.update(phase='Connecting to slave', pct=12)
        import paramiko
        from master.api.audio_bp import _slave_sftp_creds
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        try:
            sftp = c.open_sftp()
            try:
                for rel in ['slave/config/slave.cfg', 'slave/config/servo_angles.json']:
                    try:
                        os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
                        sftp.get(f'{_SLAVE_REPO}/{rel}', os.path.join(stage, rel))
                        files.append(rel)
                    except IOError:
                        pass
                snd = [n for n in sftp.listdir(_SLAVE_SOUNDS) if n.lower().endswith('.mp3') or n.endswith('.json')]
                os.makedirs(os.path.join(stage, 'slave/sounds'), exist_ok=True)
                total = max(1, len(snd))
                for i, name in enumerate(snd):
                    sftp.get(f'{_SLAVE_SOUNDS}/{name}', os.path.join(stage, 'slave/sounds', name))
                    files.append('slave/sounds/' + name)
                    job['pct'] = 12 + int(63 * (i + 1) / total)
                    job['phase'] = f'Collecting slave sounds {i + 1}/{total}'
            finally:
                sftp.close()
        finally:
            c.close()

        manifest = build_manifest(_local_version(), _robot_name(), files)
        with open(os.path.join(stage, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        job.update(phase='Compressing', pct=82)
        ts = time.strftime('%Y%m%d_%H%M%S')
        out = os.path.join(tempfile.gettempdir(), f'AstromechOS_Backup_{ts}.bck')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, fs in os.walk(stage):
                for fn in fs:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, stage).replace(os.sep, '/'))
        job.update(phase='Ready', pct=100, done=True, path=out)
    except Exception as e:
        log.exception('backup failed')
        job.update(error=str(e), done=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        job['running'] = False


@backup_bp.post('/backup/start')
@require_admin
def backup_start():
    with _backup_lock:
        if _backup_job['running']:
            return jsonify({'ok': False, 'error': 'backup already running'}), 409
        old = _backup_job.get('path')
        if old and os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass
        _backup_job.update(running=True, pct=0, phase='Starting', done=False,
                           error=None, path=None)
    threading.Thread(target=_run_backup, daemon=True, name='backup-job').start()
    return jsonify({'ok': True})


@backup_bp.get('/backup/status')
@require_admin
def backup_status():
    j = _backup_job
    return jsonify({'pct': j['pct'], 'phase': j['phase'], 'done': j['done'],
                    'error': j['error'], 'ready': bool(j.get('path'))})


@backup_bp.get('/backup/download')
@require_admin
def backup_download():
    p = _backup_job.get('path')
    if not p or not os.path.exists(p):
        return jsonify({'ok': False, 'error': 'no backup ready'}), 404

    @after_this_request
    def _cleanup(resp):
        try:
            os.remove(p)
        except OSError:
            pass
        _backup_job['path'] = None
        return resp

    return send_file(p, as_attachment=True, download_name=os.path.basename(p))


# ── Restore (B.2): streaming upload → validate/zip-slip → distribute → reboot ─
_RESTORE_MAX = 200 * 1024 * 1024  # 200 MB cap for the uploaded .bck
_RESTORE_TMP = os.path.join(tempfile.gettempdir(), 'astrorestore.bck')
_restore_lock = threading.Lock()
_restore_job = {'running': False, 'pct': 0, 'phase': '', 'done': False, 'error': None}


def _mkdirs_remote(sftp, path):
    cur = ''
    for p in [seg for seg in path.strip('/').split('/') if seg]:
        cur += '/' + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def _run_restore(bck_path):
    """Validate + anti-zip-slip, then distribute: SLAVE first (network up) →
    reboot slave over UART → master files (local.cfg MERGED so the live network
    config is preserved) → reboot master."""
    import master.registry as reg
    job = _restore_job
    stage = tempfile.mkdtemp(prefix='astrore_')
    try:
        job.update(phase='Validating', pct=5)
        with zipfile.ZipFile(bck_path) as z:
            names = z.namelist()
            if 'manifest.json' not in names:
                raise ValueError('no manifest.json — not an AstromechOS backup')
            if not validate_manifest(json.loads(z.read('manifest.json'))):
                raise ValueError('unsupported/invalid manifest')
            # Anti zip-slip: validate EVERY member before extracting anything.
            for n in names:
                if n == 'manifest.json' or n.endswith('/'):
                    continue
                if not is_safe_member(n, stage):
                    raise ValueError(f'unsafe path in archive: {n}')
            z.extractall(stage)

        from master.api.audio_bp import _slave_sftp_creds, _sftp_atomic_put

        # 1) SLAVE first (network still up), then reboot slave over UART.
        slave_root = os.path.join(stage, 'slave')
        if os.path.isdir(slave_root):
            job.update(phase='Restoring slave', pct=30)
            import paramiko
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(**_slave_sftp_creds())
            try:
                sftp = c.open_sftp()
                try:
                    for root, _, fs in os.walk(slave_root):
                        for fn in fs:
                            full = os.path.join(root, fn)
                            rel = os.path.relpath(full, slave_root).replace(os.sep, '/')
                            remote = f'{_SLAVE_REPO}/slave/{rel}'
                            _mkdirs_remote(sftp, posixpath.dirname(remote))
                            _sftp_atomic_put(sftp, remote, full)
                finally:
                    sftp.close()
            finally:
                c.close()
        try:
            if reg.uart:
                reg.uart.send('REBOOT', '1')
        except Exception:
            pass

        # 2) Master files. local.cfg is MERGED (live network sections preserved).
        job.update(phase='Restoring master', pct=65)
        master_root = os.path.join(stage, 'master')
        master_real = os.path.realpath(os.path.join(_REPO, 'master'))
        if os.path.isdir(master_root):
            for root, _, fs in os.walk(master_root):
                for fn in fs:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, master_root).replace(os.sep, '/')
                    tgt = os.path.realpath(os.path.join(_REPO, 'master', rel))
                    if tgt != master_real and not tgt.startswith(master_real + os.sep):
                        continue   # defense in depth (zip-slip already validated)
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    if rel == 'config/local.cfg':
                        backup_text = open(full, encoding='utf-8').read()
                        try:
                            live_text = open(tgt, encoding='utf-8').read()
                        except OSError:
                            live_text = ''
                        data = merge_local_cfg(backup_text, live_text)
                        tmp = tgt + '.tmp'
                        with open(tmp, 'w', encoding='utf-8') as f:
                            f.write(data)
                            f.flush()
                            try:
                                os.fsync(f.fileno())
                            except OSError:
                                pass
                        os.replace(tmp, tgt)
                    else:
                        tmp = tgt + '.tmp'
                        shutil.copy2(full, tmp)
                        os.replace(tmp, tgt)

        job.update(phase='Rebooting', pct=95, done=True)
        from master.api.status_bp import _spawn_reboot
        _spawn_reboot(['sudo', 'systemctl', 'reboot'])
    except Exception as e:
        log.exception('restore failed')
        job.update(error=str(e), done=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try:
            os.remove(bck_path)
        except OSError:
            pass
        job['running'] = False


@backup_bp.post('/restore/upload')
@require_admin
def restore_upload():
    """Stream the uploaded .bck to a temp file. Reads the raw WSGI input
    directly so Flask's 16 MB MAX_CONTENT_LENGTH (enforced on request.stream /
    form parsing) does NOT apply — a ~70 MB backup uploads fine, bounded by
    our own _RESTORE_MAX."""
    stream = request.environ.get('wsgi.input')
    if stream is None:
        return jsonify({'ok': False, 'error': 'no input stream'}), 400
    try:
        clen = int(request.environ.get('CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        clen = 0
    if clen > _RESTORE_MAX:
        return jsonify({'ok': False, 'error': 'file too large (max 200MB)'}), 413
    remaining = clen if clen > 0 else _RESTORE_MAX
    total = 0
    try:
        with open(_RESTORE_TMP, 'wb') as f:
            while remaining > 0:
                chunk = stream.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                total += len(chunk)
                if total > _RESTORE_MAX:
                    f.close()
                    os.remove(_RESTORE_TMP)
                    return jsonify({'ok': False, 'error': 'file too large (max 200MB)'}), 413
                f.write(chunk)
                remaining -= len(chunk)
    except OSError as e:
        return jsonify({'ok': False, 'error': f'upload failed: {e}'}), 500
    if not zipfile.is_zipfile(_RESTORE_TMP):
        try:
            os.remove(_RESTORE_TMP)
        except OSError:
            pass
        return jsonify({'ok': False, 'error': 'not a valid .bck (zip)'}), 400
    return jsonify({'ok': True, 'token': 'astrorestore.bck', 'bytes': total})


@backup_bp.post('/restore/apply')
@require_admin
def restore_apply():
    body = get_json_object()
    token = body.get('token') if isinstance(body, dict) else None
    if token != 'astrorestore.bck':
        return jsonify({'ok': False, 'error': 'bad token'}), 400
    if not os.path.exists(_RESTORE_TMP):
        return jsonify({'ok': False, 'error': 'no uploaded backup'}), 404
    with _restore_lock:
        if _restore_job['running']:
            return jsonify({'ok': False, 'error': 'restore already running'}), 409
        _restore_job.update(running=True, pct=0, phase='Starting', done=False, error=None)
    threading.Thread(target=_run_restore, args=(_RESTORE_TMP,), daemon=True, name='restore-job').start()
    return jsonify({'ok': True})


@backup_bp.get('/restore/status')
@require_admin
def restore_status():
    j = _restore_job
    return jsonify({'pct': j['pct'], 'phase': j['phase'], 'done': j['done'], 'error': j['error']})
