#!/usr/bin/env python3
# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
R2-D2 Joystick Stress Test + WiFi Monitor
==========================================
Simulates the real behaviour of the virtual joystick (mousemove rate) for N seconds
and simultaneously monitors the Pi to identify the cause of WiFi drops.

Usage:
    python3 tools/stress_joystick.py [--host 192.168.2.104] [--duration 30] [--rate 60]
"""

import argparse
import math
import sys
import threading
import time
import json
import urllib.request
import urllib.error
import statistics

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False
    print("[WARN] paramiko not installed -- SSH monitoring disabled")

PI_HOST  = '192.168.2.104'
PI_USER  = 'artoo'
PI_PASS  = 'deetoo'
BASE_URL = f'http://{PI_HOST}:5000'

stats = {
    'drive_sent':     0,
    'drive_ok':       0,
    'drive_err':      0,
    'drive_timeouts': 0,
    'hb_sent':        0,
    'hb_ok':          0,
    'hb_err':         0,
    'hb_timeouts':    0,
    'latencies_ms':   [],
    'start_time':     None,
}
lock        = threading.Lock()
stop_event  = threading.Event()


def post(path, body, timeout=0.5):
    url  = BASE_URL + path
    data = json.dumps(body).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={'Content-Type': 'application/json'},
                                  method='POST')
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            lat = (time.monotonic() - t0) * 1000
            return resp.status, lat
    except urllib.error.URLError as e:
        lat = (time.monotonic() - t0) * 1000
        return (-2 if 'timed out' in str(e).lower() else -1), lat
    except Exception:
        lat = (time.monotonic() - t0) * 1000
        return -1, lat


def joystick_thread(rate_hz, duration):
    """
    Simulates the propulsion joystick (arcade drive):
    - Slow full circle (4s/revolution) to reproduce diagonal movements
    - Frequency = rate_hz (simulates mousemove at N fps)
    """
    interval = 1.0 / rate_hz
    end_time = time.monotonic() + duration
    t = 0.0

    while not stop_event.is_set() and time.monotonic() < end_time:
        x = math.cos(t) * 0.8
        y = math.sin(t) * 0.8
        t += 2 * math.pi / (4.0 * rate_hz)

        throttle = -y
        steering = x
        status, lat = post('/motion/arcade', {'throttle': throttle, 'steering': steering})

        with lock:
            stats['drive_sent'] += 1
            if status == 200:
                stats['drive_ok'] += 1
                stats['latencies_ms'].append(lat)
            elif status == -2:
                stats['drive_timeouts'] += 1
            else:
                stats['drive_err'] += 1

        time.sleep(interval)

    stop_event.set()


def heartbeat_thread(duration):
    end_time = time.monotonic() + duration
    while not stop_event.is_set() and time.monotonic() < end_time:
        status, lat = post('/heartbeat', {}, timeout=0.3)
        with lock:
            stats['hb_sent'] += 1
            if status in (200, 204):
                stats['hb_ok'] += 1
            elif status == -2:
                stats['hb_timeouts'] += 1
            else:
                stats['hb_err'] += 1
        time.sleep(0.2)


SSH_CMD = r"""python3 -c "
import subprocess, json, re, time

def get_cpu():
    with open('/proc/stat') as f:
        line = f.readline().split()
    vals = [int(x) for x in line[1:]]
    return vals[3], sum(vals)

prev_idle, prev_total = get_cpu()
time.sleep(0.1)
idle, total = get_cpu()
cpu_pct = 100.0 * (1.0 - (idle - prev_idle) / max(1, total - prev_total))

def wifi_signal(iface):
    try:
        r = subprocess.run(['iwconfig', iface], capture_output=True, text=True)
        m = re.search(r'Signal level=(-?\d+)', r.stdout)
        return int(m.group(1)) if m else None
    except:
        return None

def wifi_errors(iface):
    try:
        r = subprocess.run(['ip', '-s', 'link', 'show', iface], capture_output=True, text=True)
        errs = re.findall(r'errors (\d+)', r.stdout)
        return [int(x) for x in errs]
    except:
        return []

def wifi_up(iface):
    try:
        r = subprocess.run(['ip', 'addr', 'show', iface], capture_output=True, text=True)
        return 'inet ' in r.stdout
    except:
        return False

try:
    r = subprocess.run(['dmesg', '--since', '5s ago', '-T'], capture_output=True, text=True)
    wifi_ev = [l for l in r.stdout.splitlines() if any(k in l.lower() for k in ['wlan','wifi','ieee80211','assoc','disconnect','reconnect'])]
except:
    wifi_ev = []

try:
    r2 = subprocess.run(['journalctl', '-u', 'r2d2-master.service', '--since', '3s ago', '--no-pager', '-q'], capture_output=True, text=True)
    flask_lines = [l for l in r2.stdout.splitlines() if 'motion/arcade' in l or 'heartbeat' in l or 'watchdog' in l.lower()]
    flask_hb_ok = sum(1 for l in flask_lines if 'heartbeat' in l and '204' in l)
    flask_drive = sum(1 for l in flask_lines if 'arcade' in l)
    watchdog_ev = [l for l in flask_lines if 'watchdog' in l.lower()]
except:
    flask_hb_ok = 0; flask_drive = 0; watchdog_ev = []

print(json.dumps({
    'cpu_pct':      round(cpu_pct, 1),
    'sig_wlan0':    wifi_signal('wlan0'),
    'sig_wlan1':    wifi_signal('wlan1'),
    'err_wlan0':    wifi_errors('wlan0'),
    'err_wlan1':    wifi_errors('wlan1'),
    'up_wlan0':     wifi_up('wlan0'),
    'up_wlan1':     wifi_up('wlan1'),
    'wifi_events':  wifi_ev,
    'flask_hb_ok':  flask_hb_ok,
    'flask_drive':  flask_drive,
    'watchdog_ev':  watchdog_ev,
}))
" """


def monitor_ssh_thread(duration):
    if not PARAMIKO_OK:
        return []
    samples = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
    except Exception as e:
        print(f"[SSH] Connection failed: {e}")
        return []

    end_time = time.monotonic() + duration
    while not stop_event.is_set() and time.monotonic() < end_time:
        t0 = time.monotonic()
        try:
            _, stdout, _ = ssh.exec_command(SSH_CMD, timeout=5)
            line = stdout.read().decode('utf-8', errors='replace').strip()
            d = json.loads(line)
            d['ts'] = time.monotonic() - stats['start_time']
            samples.append(d)

            up0  = 'UP' if d['up_wlan0'] else '!! DOWN !!'
            up1  = 'UP' if d['up_wlan1'] else '!! DOWN !!'
            sig0 = f"{d['sig_wlan0']}dBm" if d['sig_wlan0'] else '?'
            sig1 = f"{d['sig_wlan1']}dBm" if d['sig_wlan1'] else '?'
            err1 = d.get('err_wlan1', [])
            tx_err = err1[1] if len(err1) > 1 else 0

            with lock:
                sent = stats['drive_sent']
                errs = stats['drive_err'] + stats['drive_timeouts']
                lats = stats['latencies_ms'][-30:]
                avg_l = f"{statistics.mean(lats):.0f}ms" if lats else "?ms"

            wd = ' ⚠️ WATCHDOG: ' + d['watchdog_ev'][-1][:60] if d.get('watchdog_ev') else ''
            ev = ' ⚡ ' + d['wifi_events'][-1][:60] if d.get('wifi_events') else ''

            print(f"  t={d['ts']:5.1f}s | CPU:{d['cpu_pct']:5.1f}%"
                  f" | wlan0:{up0} {sig0} | wlan1:{up1} {sig1}"
                  f" | wlan1-TX-err:{tx_err}"
                  f" | drive:{sent} err:{errs} avg:{avg_l}"
                  f" | Pi-drive/3s:{d['flask_drive']}"
                  f"{wd}{ev}")

        except Exception as e:
            print(f"  [SSH monitor error: {e}]")

        elapsed = time.monotonic() - t0
        time.sleep(max(0, 2.0 - elapsed))

    ssh.close()
    return samples


def print_report(samples):
    with lock:
        s = stats.copy()

    elapsed = time.monotonic() - s['start_time']
    print("\n" + "=" * 65)
    print("  FINAL REPORT")
    print("=" * 65)
    print(f"  Test duration      : {elapsed:.1f}s")
    print(f"  Drive POST sent    : {s['drive_sent']}")
    print(f"  Drive OK           : {s['drive_ok']} ({100*s['drive_ok']//max(1,s['drive_sent'])}%)")
    print(f"  Drive errors       : {s['drive_err']}")
    print(f"  Drive timeouts     : {s['drive_timeouts']}")
    if s['drive_sent'] > 0:
        print(f"  Actual rate        : {s['drive_sent']/elapsed:.1f} req/s")
    if s['latencies_ms']:
        lats = s['latencies_ms']
        p95  = sorted(lats)[int(len(lats) * 0.95)]
        print(f"  Drive latency      : min={min(lats):.0f}ms avg={statistics.mean(lats):.0f}ms max={max(lats):.0f}ms p95={p95:.0f}ms")
    print(f"  Heartbeat OK       : {s['hb_ok']}/{s['hb_sent']}")
    print(f"  HB timeouts        : {s['hb_timeouts']}")

    if samples:
        drops    = [x for x in samples if not x['up_wlan1']]
        evts     = [x for x in samples if x.get('wifi_events')]
        wdogs    = [x for x in samples if x.get('watchdog_ev')]
        max_cpu  = max(x['cpu_pct'] for x in samples)
        avg_cpu  = statistics.mean(x['cpu_pct'] for x in samples)
        print(f"\n  CPU max/avg        : {max_cpu:.1f}% / {avg_cpu:.1f}%")

        if drops:
            print(f"\n  !! wlan1 DROPS detected: {len(drops)} sample(s) without IP")
            for d in drops:
                print(f"     -> t={d['ts']:.1f}s")
        else:
            print(f"\n  OK wlan1 stayed UP for the entire test")

        if wdogs:
            print(f"\n  !! Watchdog events:")
            for w in wdogs:
                for line in w['watchdog_ev']:
                    print(f"     [{w['ts']:.1f}s] {line[:100]}")

        if evts:
            print(f"\n  WiFi events kernel:")
            for ev in evts:
                for line in ev['wifi_events']:
                    print(f"     [{ev['ts']:.1f}s] {line[:100]}")

    print("\n  DIAGNOSIS:")
    with lock:
        to_rate = stats['drive_timeouts'] / max(1, stats['drive_sent']) * 100
    if to_rate > 5:
        print(f"  !! {to_rate:.1f}% of drive requests timed out -- Pi likely saturated")
    elif to_rate > 0:
        print(f"  OK {to_rate:.1f}% timeouts -- acceptable")
    else:
        print(f"  OK 0 timeouts -- Flask responding well")

    if s['hb_timeouts'] > 0:
        print(f"  !! {s['hb_timeouts']} heartbeat timeouts -- AppWatchdog could have triggered!")
    else:
        print(f"  OK heartbeat stable -- AppWatchdog would not have triggered")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',     default='192.168.2.104')
    parser.add_argument('--duration', type=int, default=30)
    parser.add_argument('--rate',     type=int, default=60,
                        help='Joystick frequency req/s (default 60 = mousemove 60fps)')
    args = parser.parse_args()

    global BASE_URL
    PI_HOST  = args.host
    BASE_URL = f'http://{PI_HOST}:5000'

    print(f"\nR2-D2 Joystick Stress Test + WiFi Monitor")
    print(f"  Target   : {BASE_URL}")
    print(f"  Duration : {args.duration}s")
    print(f"  Rate     : {args.rate} req/s  (mousemove @ {args.rate}fps = {args.rate} POST/s)")
    print(f"  + HB     : 1 req / 200ms = 5/s")
    print(f"  Total    : ~{args.rate + 5} req/s to Flask")
    print(f"  SSH mon  : {'active' if PARAMIKO_OK else 'disabled'}")
    print(f"\n  t=time | CPU% | wlan0/1 state+signal | TX-err | drive stats | Pi-side drive/3s")
    print("-" * 65)

    stats['start_time'] = time.monotonic()

    threads = [
        threading.Thread(target=joystick_thread,  args=(args.rate, args.duration), daemon=True),
        threading.Thread(target=heartbeat_thread, args=(args.duration,), daemon=True),
    ]

    samples = []
    if PARAMIKO_OK:
        def _ssh():
            nonlocal samples
            samples = monitor_ssh_thread(args.duration + 5)
        t_ssh = threading.Thread(target=_ssh, daemon=True)
        t_ssh.start()

    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join(timeout=args.duration + 5)
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        stop_event.set()

    stop_event.set()
    if PARAMIKO_OK:
        t_ssh.join(timeout=10)

    print_report(samples)


if __name__ == '__main__':
    main()
