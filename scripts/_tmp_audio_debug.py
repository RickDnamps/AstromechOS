import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)

_, out, _ = c.exec_command(
    "ssh -o StrictHostKeyChecking=no artoo@192.168.4.171 '"
    "echo === service file ===; "
    "cat /etc/systemd/system/r2d2-slave.service; "
    "echo === env of running r2d2-slave process ===; "
    "cat /proc/$(systemctl show r2d2-slave -p MainPID --value)/environ 2>/dev/null | tr '\\0' '\\n' | grep -E XDG_RUNTIME|PULSE || echo none"
    "' 2>&1",
    timeout=10
)
for line in out:
    print(line, end='')
c.close()
