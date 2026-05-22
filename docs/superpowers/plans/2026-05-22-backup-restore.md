# Backup / Restore + Server-Side Themes — Implementation Plan (Chantier B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. Sub-features B.0 → B.1 → B.2 are deployed + tested in order.

**Goal:** A Settings→System Backup/Restore tool: download `AstromechOS_Backup_<ts>.bck` (zip) of all robot state with a real % bar; restore replaces everything + reboots. Custom themes are persisted server-side first so they're backup-able + multi-device.

**Architecture:** New pure module `master/api/backup_core.py` (zip-slip guard, manifest, theme validation — dependency-free, unit-tested). New `master/api/backup_bp.py` (backup + restore endpoints, async job state). Themes server-side via `master/config/custom_themes.json` + endpoints. Reuse `_slave_sftp_creds`/`_sftp_atomic_put` (audio_bp), `write_cfg_atomic` (config_loader), `_spawn_reboot` (status_bp).

**Tech Stack:** Flask, paramiko SFTP, python `zipfile`, pytest, vanilla JS.

**Spec:** `docs/superpowers/specs/2026-05-22-backup-restore-design.md` · **Beads:** software-uhl

---

## File Structure
- **Create** `master/api/backup_core.py` — pure: `is_safe_member`, `classify_member`, `build_manifest`, `validate_manifest`, `validate_theme`, `ALLOWED_FONTS`, `BACKUP_FILESET`.
- **Create** `scripts/test_backup_core.py` — pytest.
- **Create** `master/api/backup_bp.py` — themes endpoints + backup job/endpoints + restore endpoints.
- **Modify** `master/flask_app.py` — register `backup_bp`.
- **Modify** `.gitignore` — `master/config/custom_themes.json`.
- **Modify** `master/static/js/app.js` — theme store → server; backup/restore UI. **Modify** `master/templates/index.html` — Settings→System Backup/Restore card. Sync `android/.../app.js`.

---

## Task 1 (B.0): Server-side custom themes

### 1a. Pure theme validation (TDD)
**Files:** Create `master/api/backup_core.py`, `scripts/test_backup_core.py`.

- [ ] **Step 1: Failing tests**

```python
# scripts/test_backup_core.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api.backup_core import validate_theme, is_safe_member, classify_member

def test_valid_theme():
    assert validate_theme({'id':'my-theme_1','label':'My Theme','colors':{'bg':'#101820','accent':'#00b4ff'},'font':'orbitron'})

def test_theme_bad_id():
    assert not validate_theme({'id':'../evil','label':'x','colors':{},'font':'orbitron'})

def test_theme_bad_color():
    assert not validate_theme({'id':'a','label':'x','colors':{'bg':'red; }body{'},'font':'orbitron'})

def test_theme_bad_font():
    assert not validate_theme({'id':'a','label':'x','colors':{'bg':'#fff'},'font':'comic-sans'})

def test_theme_label_xss_string_allowed_value_but_capped():
    assert not validate_theme({'id':'a','label':'x'*41,'colors':{'bg':'#fff'},'font':'orbitron'})
```

- [ ] **Step 2: Run → fail** (`python -m pytest scripts/test_backup_core.py -v` → ModuleNotFound)

- [ ] **Step 3: Implement** `master/api/backup_core.py` (validation part)

```python
"""Pure helpers for Backup/Restore + themes. No Flask/paramiko/FS side effects
beyond path math — unit-testable in isolation."""
from __future__ import annotations
import os, posixpath, re

ALLOWED_FONTS = {'orbitron', 'share_tech_mono', 'audiowide', 'electrolize',
                 'exo2', 'rajdhani', 'courier'}
_THEME_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{3,8}$')

def validate_theme(t) -> bool:
    if not isinstance(t, dict):
        return False
    if not isinstance(t.get('id'), str) or not _THEME_ID_RE.match(t['id']):
        return False
    if not isinstance(t.get('label'), str) or not (1 <= len(t['label']) <= 40):
        return False
    colors = t.get('colors')
    if not isinstance(colors, dict) or not colors or len(colors) > 20:
        return False
    for v in colors.values():
        if not (isinstance(v, str) and _HEX_RE.match(v)):
            return False
    font = t.get('font')
    if font is not None and font not in ALLOWED_FONTS:
        return False
    return True
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** (`git commit -m "Feat: pure theme validation (chantier B)"`).

### 1b. Themes endpoints + storage
**Files:** Create `master/api/backup_bp.py` (themes part); modify `flask_app.py`, `.gitignore`.

- [ ] **Step 1:** Add `master/config/custom_themes.json` to `.gitignore` (under the runtime working block).

- [ ] **Step 2:** Create `backup_bp.py` with the themes API:

```python
import json, os, threading, logging
from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin, get_json_object
from master.api.backup_core import validate_theme
from master.config.config_loader import CONFIG_DIR  # or compute from __file__

log = logging.getLogger(__name__)
backup_bp = Blueprint('backup', __name__)
_THEMES_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'custom_themes.json')
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
    tmp = _THEMES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'themes': themes}, f, indent=2, ensure_ascii=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, _THEMES_FILE)

@backup_bp.get('/themes/custom')
def themes_list():
    return jsonify({'themes': _read_themes()})

@backup_bp.post('/themes/custom')
@require_admin
def themes_save():
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

@backup_bp.delete('/themes/custom/<tid>')
@require_admin
def themes_delete(tid):
    with _themes_lock:
        themes = [t for t in _read_themes() if t.get('id') != tid]
        _write_themes(themes)
    return jsonify({'ok': True})
```

- [ ] **Step 3:** Register in `flask_app.py` (add `from master.api.backup_bp import backup_bp` near line 87 and `app.register_blueprint(backup_bp)` near line 100).

- [ ] **Step 4:** `python -c "import ast; ast.parse(open('master/api/backup_bp.py',encoding='utf-8').read())"`; commit.

### 1c. Frontend: themes save to server
**Files:** `master/static/js/app.js` (+ android sync).

- [ ] **Step 1:** In `_saveCustomThemesStore(list)` also POST each new theme to `/themes/custom` via `api()` (keep localStorage as write-through cache). In `_loadCustomThemes()` prefer server (`GET /themes/custom`); on first load, if server empty + localStorage non-empty, migrate (POST each) then use server. `deleteCustomTheme(id)` calls `DELETE /themes/custom/<id>`. Confirm helper names by grepping app.js (lines ~207-410). Render labels via `textContent`.
- [ ] **Step 2:** `node --check master/static/js/app.js`; `cp` to android; commit.

---

## Task 2 (B.1): Backup (async job + % bar)

### 2a. Manifest + fileset (pure, TDD)
- [ ] **Step 1: Failing tests** (append to `scripts/test_backup_core.py`)

```python
from master.api.backup_core import build_manifest, validate_manifest, BACKUP_FILESET

def test_manifest_roundtrip():
    m = build_manifest(astromech_version='abc1234', robot_name='R2-D2', files=['master/config/local.cfg'])
    assert m['format_version'] == 1 and m['robot_name'] == 'R2-D2'
    assert validate_manifest(m) is True

def test_validate_manifest_rejects_bad():
    assert validate_manifest({}) is False
    assert validate_manifest({'format_version': 999}) is False

def test_fileset_has_master_and_slave():
    assert any(p.startswith('master/') for p in BACKUP_FILESET['master'])
    assert any(p.startswith('slave/') for p in BACKUP_FILESET['slave'])
```

- [ ] **Step 2: Run → fail. Step 3: Implement** (append to `backup_core.py`)

```python
import datetime

_SUPPORTED_FORMAT = 1
# Paths relative to repo root. Dirs end with '/'. Master collected locally;
# slave collected via SFTP.
BACKUP_FILESET = {
    'master': [
        'master/config/local.cfg', 'master/config/choreo_categories.json',
        'master/config/shortcuts.json', 'master/config/bt_config.json',
        'master/config/dome_angles.json', 'master/config/camera.env',
        'master/config/custom_themes.json',
        'master/choreographies/', 'master/light_sequences/', 'master/sequences/',
    ],
    'slave': [
        'slave/config/slave.cfg', 'slave/config/servo_angles.json', 'slave/sounds/',
    ],
}

def build_manifest(astromech_version: str, robot_name: str, files: list) -> dict:
    return {
        'format_version': _SUPPORTED_FORMAT,
        'created': datetime.datetime.now().isoformat(timespec='seconds'),
        'astromech_version': astromech_version,
        'robot_name': robot_name,
        'files': sorted(files),
    }

def validate_manifest(m) -> bool:
    return isinstance(m, dict) and m.get('format_version') == _SUPPORTED_FORMAT \
        and isinstance(m.get('files'), list)
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**

### 2b. Backup job + endpoints
**Files:** `master/api/backup_bp.py`.

- [ ] **Step 1:** Add the job-state + endpoints. Reuse `_slave_sftp_creds` from audio_bp.

```python
import io, time, zipfile, tempfile, shutil, configparser
from flask import send_file, after_this_request
import master.registry as reg
from master.api.audio_bp import _slave_sftp_creds
from master.api.backup_core import BACKUP_FILESET, build_manifest
from shared.paths import SLAVE_SOUNDS as _SLAVE_SOUNDS  # remote slave paths

_REPO = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
_SLAVE_REPO = '/home/artoo/astromechos'   # remote; or read from cfg [slave]
_backup_lock = threading.Lock()
_backup_job = {'running': False, 'pct': 0, 'phase': '', 'done': False, 'error': None, 'path': None}

def _robot_name():
    cfg = configparser.ConfigParser(); cfg.read([os.path.join(_REPO,'master/config/main.cfg'), os.path.join(_REPO,'master/config/local.cfg')])
    return cfg.get('robot', 'name', fallback='AstromechOS')

def _run_backup():
    job = _backup_job
    stage = tempfile.mkdtemp(prefix='astrobk_')
    try:
        files = []
        job.update(phase='Collecting master', pct=5)
        for rel in BACKUP_FILESET['master']:
            src = os.path.join(_REPO, rel)
            if rel.endswith('/'):
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(stage, rel), dirs_exist_ok=True)
                    files += [rel + f for f in os.listdir(src)]
            elif os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
                shutil.copy2(src, os.path.join(stage, rel)); files.append(rel)
        # slave via SFTP
        job.update(phase='Collecting slave', pct=15)
        import paramiko
        c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        try:
            sftp = c.open_sftp()
            try:
                # configs
                for rel in ['slave/config/slave.cfg', 'slave/config/servo_angles.json']:
                    try:
                        os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
                        sftp.get(f'{_SLAVE_REPO}/{rel}', os.path.join(stage, rel)); files.append(rel)
                    except IOError:
                        pass
                # sounds (the long phase)
                snd = sftp.listdir(_SLAVE_SOUNDS)
                os.makedirs(os.path.join(stage, 'slave/sounds'), exist_ok=True)
                for i, name in enumerate(snd):
                    sftp.get(f'{_SLAVE_SOUNDS}/{name}', os.path.join(stage, 'slave/sounds', name))
                    files.append('slave/sounds/' + name)
                    job['pct'] = 15 + int(60 * (i + 1) / max(1, len(snd)))
                    job['phase'] = f'Collecting slave sounds {i+1}/{len(snd)}'
            finally:
                sftp.close()
        finally:
            c.close()
        # manifest
        manifest = build_manifest(reg.version if hasattr(reg,'version') else 'unknown', _robot_name(), files)
        with open(os.path.join(stage, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        # zip
        job.update(phase='Compressing', pct=80)
        ts = time.strftime('%Y%m%d_%H%M%S')
        out = os.path.join(tempfile.gettempdir(), f'AstromechOS_Backup_{ts}.bck')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, fs in os.walk(stage):
                for fn in fs:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, stage))
        job.update(phase='Ready', pct=100, done=True, path=out)
    except Exception as e:
        log.exception('backup failed'); job.update(error=str(e), done=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        job['running'] = False

@backup_bp.post('/backup/start')
@require_admin
def backup_start():
    with _backup_lock:
        if _backup_job['running']:
            return jsonify({'ok': False, 'error': 'backup already running'}), 409
        _backup_job.update(running=True, pct=0, phase='Starting', done=False, error=None, path=None)
    threading.Thread(target=_run_backup, daemon=True, name='backup-job').start()
    return jsonify({'ok': True})

@backup_bp.get('/backup/status')
@require_admin
def backup_status():
    j = _backup_job
    return jsonify({'pct': j['pct'], 'phase': j['phase'], 'done': j['done'], 'error': j['error']})

@backup_bp.get('/backup/download')
@require_admin
def backup_download():
    p = _backup_job.get('path')
    if not p or not os.path.exists(p):
        return jsonify({'ok': False, 'error': 'no backup ready'}), 404
    @after_this_request
    def _cleanup(resp):
        try: os.remove(p)
        except OSError: pass
        _backup_job['path'] = None
        return resp
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))
```

- [ ] **Step 2:** ast-parse; commit.

### 2c. Backup frontend
**Files:** `index.html` (Settings→System card), `app.js`.

- [ ] **Step 1:** Add a "Create backup" button + a progress-bar `<div>` in the SYSTEM card (reuse existing `.settings-card` / progress classes — grep first). Handler: POST `/backup/start` → poll `/backup/status` every 1s, set bar width = `pct`, show `phase` (via `textContent`); on `done` without error → `window.location = '/backup/download'` (or an `<a download>` click) + success toast; on error → toast. Use `apiDetail` with a long timeout for start.
- [ ] **Step 2:** `node --check`; sync android; commit.

---

## Task 3 (B.2): Restore (streaming upload + apply + reboot)

### 3a. Zip-slip guard + classify (pure, TDD — SECURITY CRITICAL)
- [ ] **Step 1: Failing tests** (append to `scripts/test_backup_core.py`)

```python
import os
def test_zipslip_safe(tmp_path):
    root = str(tmp_path)
    assert is_safe_member('master/config/local.cfg', root) is True
    assert is_safe_member('slave/sounds/A.mp3', root) is True

def test_zipslip_blocks_escape(tmp_path):
    root = str(tmp_path)
    assert is_safe_member('../etc/passwd', root) is False
    assert is_safe_member('/etc/passwd', root) is False
    assert is_safe_member('master/../../etc/x', root) is False
    assert is_safe_member('master/sounds/../../../x', root) is False
    assert is_safe_member('', root) is False

def test_classify_member():
    assert classify_member('master/config/local.cfg') == ('master', 'config/local.cfg')
    assert classify_member('slave/sounds/A.mp3') == ('slave', 'sounds/A.mp3')
    assert classify_member('manifest.json') == (None, None)
    assert classify_member('evil.sh') == (None, None)

def test_merge_local_cfg_preserves_network():
    from master.api.backup_core import merge_local_cfg
    backup = "[hotspot]\nssid = OLD_AP\npassword = oldpass\n[robot]\nname = R2-D2\n"
    live   = "[hotspot]\nssid = LIVE_AP\npassword = livepass\n[robot]\nname = OldName\n"
    out = merge_local_cfg(backup, live)
    assert 'LIVE_AP' in out and 'livepass' in out      # network kept from LIVE
    assert 'OLD_AP' not in out and 'oldpass' not in out # backup network dropped
    assert 'name = R2-D2' in out                        # content restored from backup
```

- [ ] **Step 2: Run → fail. Step 3: Implement** (append to `backup_core.py`)

```python
def is_safe_member(member_name: str, dest_root: str) -> bool:
    """Anti zip-slip: True only if extracting member_name stays within dest_root."""
    if not member_name or member_name.startswith(('/', '\\')) or os.path.isabs(member_name):
        return False
    norm = posixpath.normpath(member_name.replace('\\', '/'))
    if norm == '..' or norm.startswith('../') or '/../' in norm:
        return False
    root = os.path.realpath(dest_root)
    target = os.path.realpath(os.path.join(root, *norm.split('/')))
    return target == root or target.startswith(root + os.sep)

def classify_member(member_name: str):
    """('master'|'slave', relpath) for an allowed .bck member, else (None, None)."""
    parts = member_name.replace('\\', '/').split('/')
    if len(parts) >= 2 and parts[0] in ('master', 'slave') and '..' not in parts:
        return parts[0], '/'.join(parts[1:])
    return None, None

# Network/infra sections of local.cfg PRESERVED from the live machine on restore
# (never taken from the backup) — keeps master<->slave WiFi + SSH from breaking.
NETWORK_PRESERVE_SECTIONS = {'home_wifi', 'hotspot', 'deploy', 'slave', 'github'}

def merge_local_cfg(backup_text: str, live_text: str) -> str:
    """Return a local.cfg = backup content, but with NETWORK_PRESERVE_SECTIONS
    taken from the LIVE config (so a restore never changes the AP/WiFi/SSH/slave
    host). Pure string->string (configparser in-memory)."""
    import configparser, io
    bak = configparser.ConfigParser(); bak.optionxform = str; bak.read_string(backup_text)
    live = configparser.ConfigParser(); live.optionxform = str; live.read_string(live_text or '')
    for sec in NETWORK_PRESERVE_SECTIONS:
        bak.remove_section(sec)               # drop backup's network sections
        if live.has_section(sec):             # ...replace with the live ones
            bak.add_section(sec)
            for k, v in live.items(sec):
                bak.set(sec, k, v)
    out = io.StringIO(); bak.write(out)
    return out.getvalue()
```

- [ ] **Step 4: Run → pass. Step 5: Commit.**

### 3b. Restore endpoints (streaming upload, apply job, reboot)
**Files:** `master/api/backup_bp.py`.

- [ ] **Step 1:** Streaming upload (bypasses the 16 MB form cap by reading `request.stream`):

```python
_RESTORE_MAX = 200 * 1024 * 1024  # 200 MB cap for the .bck upload
_restore_job = {'running': False, 'pct': 0, 'phase': '', 'done': False, 'error': None}

@backup_bp.post('/restore/upload')
@require_admin
def restore_upload():
    dest = os.path.join(tempfile.gettempdir(), 'astrorestore.bck')
    total = 0
    with open(dest, 'wb') as f:
        while True:
            chunk = request.stream.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > _RESTORE_MAX:
                f.close(); os.remove(dest)
                return jsonify({'ok': False, 'error': 'file too large'}), 413
            f.write(chunk)
    # quick sanity: is it a zip?
    if not zipfile.is_zipfile(dest):
        os.remove(dest); return jsonify({'ok': False, 'error': 'not a valid .bck (zip)'}), 400
    return jsonify({'ok': True, 'token': 'astrorestore.bck', 'bytes': total})
```

- [ ] **Step 2:** Apply job (validate manifest + zip-slip + distribute + reboot):

```python
from master.api.backup_core import is_safe_member, classify_member, validate_manifest
from master.api.audio_bp import _sftp_atomic_put

def _run_restore(bck_path):
    job = _restore_job
    stage = tempfile.mkdtemp(prefix='astrore_')
    try:
        job.update(phase='Validating', pct=5)
        with zipfile.ZipFile(bck_path) as z:
            names = z.namelist()
            if 'manifest.json' not in names:
                raise ValueError('no manifest.json')
            manifest = json.loads(z.read('manifest.json'))
            if not validate_manifest(manifest):
                raise ValueError('unsupported/invalid manifest')
            # anti zip-slip: validate ALL members before extracting anything
            for n in names:
                if n == 'manifest.json':
                    continue
                if not is_safe_member(n, stage):
                    raise ValueError(f'unsafe path in archive: {n}')
            z.extractall(stage)   # safe: all members validated above
        # ORDER (network-safety): SLAVE first (network still up) -> reboot slave
        # over UART -> master files (local.cfg MERGED) -> reboot master.
        from master.api.backup_core import merge_local_cfg
        slave_root = os.path.join(stage, 'slave')
        if os.path.isdir(slave_root):
            job.update(phase='Restoring slave', pct=30)
            import paramiko
            c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(**_slave_sftp_creds())
            try:
                sftp = c.open_sftp()
                try:
                    for root, _, fs in os.walk(slave_root):
                        for fn in fs:
                            full = os.path.join(root, fn)
                            rel = os.path.relpath(full, slave_root).replace('\\', '/')
                            remote = f'{_SLAVE_REPO}/slave/{rel}'
                            _mkdirs_remote(sftp, os.path.dirname(remote))
                            _sftp_atomic_put(sftp, remote, full)
                finally:
                    sftp.close()
            finally:
                c.close()
        # Reboot the slave NOW (UART — works regardless of WiFi). It rejoins the
        # UNCHANGED AP on its own (slave network config is OS-level, not restored).
        try:
            if reg.uart: reg.uart.send('REBOOT', '1')
        except Exception:
            pass

        job.update(phase='Restoring master', pct=65)
        master_root = os.path.join(stage, 'master')
        master_real = os.path.realpath(os.path.join(_REPO, 'master'))
        for root, _, fs in os.walk(master_root):
            for fn in fs:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, master_root).replace('\\', '/')
                tgt = os.path.realpath(os.path.join(_REPO, 'master', rel))
                if tgt != master_real and not tgt.startswith(master_real + os.sep):
                    continue   # defense in depth (zip-slip already validated)
                os.makedirs(os.path.dirname(tgt), exist_ok=True)
                if rel == 'config/local.cfg':
                    # MERGE: backup content + LIVE network sections (never sever
                    # master<->slave WiFi / SSH).
                    backup_text = open(full, encoding='utf-8').read()
                    try:
                        live_text = open(tgt, encoding='utf-8').read()
                    except OSError:
                        live_text = ''
                    merged = merge_local_cfg(backup_text, live_text)
                    tmp = tgt + '.tmp'
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(merged); f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, tgt)
                else:
                    tmp = tgt + '.tmp'; shutil.copy2(full, tmp); os.replace(tmp, tgt)
        job.update(phase='Rebooting', pct=95, done=True)
        from master.api.status_bp import _spawn_reboot
        _spawn_reboot(['sudo', 'systemctl', 'reboot'])
    except Exception as e:
        log.exception('restore failed'); job.update(error=str(e), done=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try: os.remove(bck_path)
        except OSError: pass
        job['running'] = False

def _mkdirs_remote(sftp, path):
    parts = path.strip('/').split('/'); cur = ''
    for p in parts:
        cur += '/' + p
        try: sftp.stat(cur)
        except IOError:
            try: sftp.mkdir(cur)
            except IOError: pass

@backup_bp.post('/restore/apply')
@require_admin
def restore_apply():
    body = get_json_object(); token = body.get('token') if isinstance(body, dict) else None
    if token != 'astrorestore.bck':
        return jsonify({'ok': False, 'error': 'bad token'}), 400
    bck = os.path.join(tempfile.gettempdir(), 'astrorestore.bck')
    if not os.path.exists(bck):
        return jsonify({'ok': False, 'error': 'no uploaded backup'}), 404
    with _backup_lock:
        if _restore_job['running']:
            return jsonify({'ok': False, 'error': 'restore already running'}), 409
        _restore_job.update(running=True, pct=0, phase='Starting', done=False, error=None)
    threading.Thread(target=_run_restore, args=(bck,), daemon=True, name='restore-job').start()
    return jsonify({'ok': True})

@backup_bp.get('/restore/status')
@require_admin
def restore_status():
    j = _restore_job
    return jsonify({'pct': j['pct'], 'phase': j['phase'], 'done': j['done'], 'error': j['error']})
```

- [ ] **Step 3:** ast-parse; commit.

### 3c. Restore frontend
- [ ] **Step 1:** In the SYSTEM card add a Restore file-input + button. Flow: confirm modal ("OVERWRITES everything + reboots — type RESTORE / click confirm"; offer "download a safety backup first"). On confirm: `fetch('/restore/upload', {method:'POST', body:file, headers:{'X-Admin-Pw':token}})` (raw body, NOT FormData → streams) → on ok, POST `/restore/apply` {token} → poll `/restore/status` bar → on `phase==='Rebooting'` show the existing reboot-countdown overlay → poll `/status` until reconnect → `location.reload()`. Render phase via `textContent`.
- [ ] **Step 2:** `node --check`; sync android; commit.

---

## Task 4: Deploy + live round-trip test

- [ ] **Step 1:** Deploy (`update.sh` via paramiko). Confirm master at the new HEAD, services active, `/themes/custom` + `/backup/status` reachable.
- [ ] **Step 2:** **Theme round-trip**: create a custom theme in the UI → confirm `master/config/custom_themes.json` on the master has it → delete → gone.
- [ ] **Step 3:** **Backup**: trigger backup → bar advances through phases → `.bck` downloads → unzip locally → assert `manifest.json` + `master/` + `slave/sounds/` (321) present.
- [ ] **Step 4:** **Restore round-trip (CAREFUL — reboots; keep the chantier-A safety backups)**: change one thing (e.g., add a test sound), restore the `.bck` from Step 3, let it reboot, verify the test sound is gone (state matches the backup) + 321 sounds + calibration md5 matches.
- [ ] **Step 5:** **Zip-slip live**: `POST /restore/apply` with a hand-crafted `.bck` containing a `../../tmp/evil` member → must be rejected, nothing written outside targets.

## Task 5: Security audit
- [ ] Dispatch a review agent over `backup_core.py`, `backup_bp.py`, the frontend, `flask_app.py`. Focus: **zip-slip** (every member validated before extract; `extractall` only after the loop; symlink members), **path containment** on master writes + slave SFTP, **admin auth** on all mutating endpoints, the **streaming upload** size cap + temp cleanup, single-job locks, no secret leak beyond the intended `.bck`. Fix findings, re-deploy, document.

---

## Self-Review
- **Spec coverage:** themes server-side (T1) ✓ · backup async %+download (T2) ✓ · restore stream-upload+apply+reboot (T3) ✓ · zip-slip + manifest + theme validation pure+tested (T1a,T2a,T3a) ✓ · 16 MB-cap bypass via streaming (T3b) ✓ · security audit (T5) ✓ · round-trip + zip-slip tests (T4) ✓.
- **Placeholders:** none — complete code for pure logic + endpoints; frontend steps name the exact endpoints + flow (helper names to be grep-confirmed, deliberate).
- **Consistency:** `_backup_job`/`_restore_job` state keys (`pct/phase/done/error`), `is_safe_member(member,root)`, `classify_member`, `validate_manifest`, `build_manifest`, `BACKUP_FILESET`, token `'astrorestore.bck'` used consistently across tasks.
