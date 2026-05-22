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
from master.api.backup_core import validate_theme, BACKUP_FILESET, build_manifest
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
