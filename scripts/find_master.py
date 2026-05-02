#!/usr/bin/env python3
# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
# -*- coding: utf-8 -*-
"""
Find the IP of r2-master from Windows.
Tries mDNS first, then SSH scan on the local subnet.
Usage: python3 scripts/find_master.py
"""
import socket
import concurrent.futures
import sys

# Windows cp1252 : forcer UTF-8 sur stdout
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def _try_mdns(hostname='r2-master.local', timeout=2) -> str | None:
    try:
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception:
        return None


def _get_local_subnet() -> str | None:
    """Return the local subnet prefix (e.g. '192.168.2.')."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return '.'.join(ip.split('.')[:3]) + '.'
    except Exception:
        return None


def _scan_ssh(prefix: str, port=22, timeout=0.5) -> list[str]:
    """SSH scan across all IPs on the subnet."""
    def check(ip):
        s = socket.socket()
        s.settimeout(timeout)
        r = s.connect_ex((ip, port))
        s.close()
        return ip if r == 0 else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        results = list(ex.map(check, [f'{prefix}{i}' for i in range(2, 255)]))
    return [ip for ip in results if ip]


def find_master() -> str | None:
    # 1. mDNS attempt
    print('Trying mDNS r2-master.local...', end=' ', flush=True)
    ip = _try_mdns()
    if ip:
        print(f'found → {ip}')
        return ip
    print('failed')

    # 2. SSH scan on the subnet
    prefix = _get_local_subnet()
    if not prefix:
        print('Unable to determine the local subnet')
        return None
    print(f'SSH scan on {prefix}0/24...', end=' ', flush=True)
    hosts = _scan_ssh(prefix)
    if not hosts:
        print('no SSH host found')
        return None
    print(f'{len(hosts)} SSH host(s): {hosts}')

    # Single SSH host → most likely the Pi
    if len(hosts) == 1:
        print(f'→ r2-master probably at {hosts[0]}')
        return hosts[0]

    # Multiple hosts → display the list, let the user choose
    print('Multiple SSH hosts found. Which one is r2-master?')
    for i, h in enumerate(hosts):
        print(f'  [{i}] {h}')
    return None


if __name__ == '__main__':
    ip = find_master()
    if ip:
        print(f'\nr2-master IP: {ip}')
        sys.exit(0)
    else:
        print('\nNot found')
        sys.exit(1)
