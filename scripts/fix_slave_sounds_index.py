"""Diagnose + repair slave/sounds_index.json corruption.
Loads the Master's canonical copy, validates it, and SFTPs it to the
Slave atomically. Then restarts the slave service so AudioDriver picks
it up. Triggered after a corrupted index left audio silently disabled."""
import json, os, sys, paramiko

MASTER_HOST  = '192.168.2.104'
MASTER_USER  = 'artoo'
MASTER_PASS  = 'deetoo'
MASTER_INDEX = '/home/artoo/astromechos/master/sounds_index.json'
SLAVE_HOST   = 'r2-slave.local'
SLAVE_INDEX  = '/home/artoo/astromechos/slave/sounds_index.json'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(MASTER_HOST, username=MASTER_USER, password=MASTER_PASS, timeout=10)

# 1. Read Master canonical
sftp = c.open_sftp()
with sftp.open(MASTER_INDEX, 'rb') as f:
    master_bytes = f.read()
sftp.close()
print(f'Master index: {len(master_bytes)} bytes')
try:
    master_obj = json.loads(master_bytes)
    cats = master_obj.get('categories', {})
    total = sum(len(v) for v in cats.values())
    print(f'  parsed OK: {len(cats)} categories, {total} sounds')
except json.JSONDecodeError as e:
    print(f'  MASTER ALSO CORRUPT: {e}')
    sys.exit(1)

# 2. Read Slave's broken copy via SSH chain
stdin, stdout, _ = c.exec_command(
    f'ssh -o ConnectTimeout=5 artoo@{SLAVE_HOST} "wc -c {SLAVE_INDEX}; python3 -c \\\"import json; json.load(open(\\\\\\\"{SLAVE_INDEX}\\\\\\\"))\\\" 2>&1 | head -2"',
    timeout=15,
)
print('=== Slave current state:')
print(stdout.read().decode())

# 3. SCP the canonical Master copy to Slave (atomic via .tmp + mv)
print('=== Pushing Master canonical to Slave...')
import time
remote_tmp = SLAVE_INDEX + '.tmp'
# Write via SSH heredoc — paramiko's SFTP can't chain through to slave directly
import base64
b64 = base64.b64encode(master_bytes).decode()
push_cmd = (
    f'ssh -o ConnectTimeout=5 artoo@{SLAVE_HOST} '
    f'"echo {b64} | base64 -d > {remote_tmp} && '
    f'python3 -c \\\"import json; json.load(open(\\\\\\\"{remote_tmp}\\\\\\\"))\\\" && '
    f'mv {remote_tmp} {SLAVE_INDEX} && echo OK_PUSHED"'
)
stdin, stdout, stderr = c.exec_command(push_cmd, timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
print('STDOUT:', out)
if err.strip():
    print('STDERR:', err)

if 'OK_PUSHED' not in out:
    print('!!! push failed — slave index NOT updated')
    sys.exit(1)

# 4. Restart slave service
print('=== Restarting slave service...')
c.exec_command(f'ssh artoo@{SLAVE_HOST} "sudo systemctl restart astromech-slave"', timeout=10)
time.sleep(4)

# 5. Verify AudioDriver came up
stdin, stdout, _ = c.exec_command(
    f'ssh artoo@{SLAVE_HOST} "sudo journalctl -u astromech-slave --no-pager -n 30 2>&1 | grep -iE \\\"audio|S:|launch|register\\\""',
    timeout=15,
)
print('=== Slave audio init logs:')
print(stdout.read().decode())
c.close()
print('=== Done. Try /audio/play now.')
