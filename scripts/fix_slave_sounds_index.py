"""Diagnose + repair slave/sounds_index.json corruption.

Run ON THE MASTER (no Master SSH needed — direct local file access; uses
key-based SSH to the Slave, set up by setup_ssh_keys.sh). Loads the
Master's canonical copy, validates it, and pushes it to the Slave
atomically. Then restarts the slave service so AudioDriver picks it up.

Usage: python3 scripts/fix_slave_sounds_index.py

Portability chantier 2026-05-28: was hardcoded 'artoo' + 'deetoo'
plaintext password + '/home/artoo/...' paths. Now derives the repo
root from __file__ and the SSH target from shared/identity.py."""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

# Repo root is two levels up from this script (scripts/<this file>).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from shared.identity import slave_ssh_target  # noqa: E402

MASTER_INDEX = REPO_ROOT / 'master' / 'sounds_index.json'
SLAVE = slave_ssh_target()
# Path on the slave — $HOME/astromechos by convention (the install scripts
# always lay it out under the user's home). Single-quoted so the shell on
# the slave expands $HOME, not the local shell.
SLAVE_INDEX = '$HOME/astromechos/slave/sounds_index.json'

SSH = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', SLAVE]


def _ssh(cmd: str, timeout: float = 15.0) -> subprocess.CompletedProcess:
    return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=timeout)


# 1. Read Master canonical
print(f'Master index ({MASTER_INDEX}):')
if not MASTER_INDEX.is_file():
    print(f'  !!! file not found: {MASTER_INDEX}')
    sys.exit(1)
master_bytes = MASTER_INDEX.read_bytes()
print(f'  {len(master_bytes)} bytes')
try:
    master_obj = json.loads(master_bytes)
    cats = master_obj.get('categories', {})
    total = sum(len(v) for v in cats.values())
    print(f'  parsed OK: {len(cats)} categories, {total} sounds')
except json.JSONDecodeError as e:
    print(f'  MASTER ALSO CORRUPT: {e}')
    sys.exit(1)

# 2. Inspect Slave current state
print('=== Slave current state:')
r = _ssh(f'wc -c {SLAVE_INDEX} 2>&1; '
         f'python3 -c "import json; json.load(open(\\"{SLAVE_INDEX}\\"))" 2>&1 | head -2')
print(r.stdout, r.stderr, sep='')

# 3. Push canonical to Slave atomically (tmp + validate + rename)
print('=== Pushing Master canonical to Slave...')
remote_tmp = SLAVE_INDEX + '.tmp'
b64 = base64.b64encode(master_bytes).decode()
push = (
    f'echo {b64} | base64 -d > {remote_tmp} && '
    f'python3 -c "import json; json.load(open(\\"{remote_tmp}\\"))" && '
    f'mv {remote_tmp} {SLAVE_INDEX} && echo OK_PUSHED'
)
r = _ssh(push, timeout=30)
print('STDOUT:', r.stdout)
if r.stderr.strip():
    print('STDERR:', r.stderr)
if 'OK_PUSHED' not in r.stdout:
    print('!!! push failed — slave index NOT updated')
    sys.exit(1)

# 4. Restart slave service
print('=== Restarting slave service...')
_ssh('sudo systemctl restart astromech-slave', timeout=10)
time.sleep(4)

# 5. Verify AudioDriver came up
print('=== Slave audio init logs:')
r = _ssh(
    'sudo journalctl -u astromech-slave --no-pager -n 30 2>&1 '
    '| grep -iE "audio|S:|launch|register"',
)
print(r.stdout)
print('=== Done. Try /audio/play now.')
