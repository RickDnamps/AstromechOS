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
"""
Test unitaire checksum UART — somme + longueur mod 256.
Phase 1: tests locaux, pas de hardware requis.
"""
import sys, logging
sys.path.insert(0, '/home/artoo/r2d2')
from shared.uart_protocol import calc_crc, build_msg, parse_msg

PASS = []; FAIL = []
WARNS = []

class Cap(logging.Handler):
    def emit(self, r): WARNS.append(self.format(r))
h = Cap()
h.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger().addHandler(h)
logging.getLogger().setLevel(logging.WARNING)


def chk(name, got, expected):
    if got == expected:
        PASS.append(name)
        print('  PASS  ' + name)
    else:
        FAIL.append(name)
        print('  FAIL  ' + name)
        print('        got      = ' + repr(got))
        print('        expected = ' + repr(expected))


print()
print('=' * 64)
print(' PHASE 1 — TESTS UNITAIRES  (somme + longueur mod 256)')
print('=' * 64)

# ── 0. Valeurs de reference ──────────────────────────────────────────────────
print()
print('[0] Valeurs de reference checksum:')
ref = [('H', '1'), ('H', 'OK'), ('M', '0.500,0.500'), ('S', 'Happy001'),
       ('TL', '24.0:35.2:8.5:1200:0.45:0')]
for t, v in ref:
    p = t + ':' + v
    d = p.encode()
    cs = calc_crc(p)
    print('  ' + repr(p) + ' sum=' + str(sum(d)) + ' len=' + str(len(d))
          + ' -> (' + str(sum(d)) + '+' + str(len(d)) + ')%256='
          + str((sum(d) + len(d)) % 256) + '=0x' + cs)

# ── 1. Round-trip build -> parse ─────────────────────────────────────────────
print()
print('[1.1] Round-trip build -> parse (messages valides)')
for t, v in [
    ('H',  '1'),
    ('H',  'OK'),
    ('M',  '0.500,0.500'),
    ('M',  '-0.800,-0.800'),
    ('S',  'Happy001'),
    ('TL', '24.0:35.2:8.5:1200:0.45:0'),
    ('TR', '23.8:36.1:7.9:1180:0.43:0'),
    ('CANFOUND', '1,2'),
    ('V',  'abc123'),
    ('DISP', 'TELEM:24.0V:35C'),
]:
    r = parse_msg(build_msg(t, v).strip())
    chk(t + ':' + v, r, (t, v))

# ── 2. Bit flip ───────────────────────────────────────────────────────────────
print()
print('[1.2] Bit flip dans le payload')
for t, v, pos in [
    ('H',  '1',                    2),
    ('M',  '0.500,0.500',          4),
    ('S',  'Happy001',             3),
    ('TL', '24.0:35.2:8.5:1200',  5),
]:
    orig = build_msg(t, v).strip()
    bad  = orig[:pos] + chr(ord(orig[pos]) ^ 0x01) + orig[pos+1:]
    chk('bit_flip@' + str(pos) + ' ' + orig + '->' + bad, parse_msg(bad), None)

# ── 3. Injection zero — BUG CORRIGE ──────────────────────────────────────────
print()
print('[1.3] Injection zero (x00) — CORRIGE par +len (ancien bug: passait avec sum seul)')
for t, v in [('H', '1'), ('M', '0.500,0.500'), ('TL', '24.0:35.2:8.5:1200:0.45:0')]:
    orig = build_msg(t, v).strip()
    # Injection au milieu du payload (avant le dernier :CS)
    bad  = orig[:3] + chr(0) + orig[3:]
    # Montrer que sum seul n'aurait pas detecte:
    p_orig = t + ':' + v
    p_bad  = (t + ':' + chr(0) + v)
    sum_only_orig = sum(p_orig.encode()) % 256
    sum_only_bad  = sum(p_bad.encode()) % 256
    sum_len_orig  = (sum(p_orig.encode()) + len(p_orig.encode())) % 256
    sum_len_bad   = (sum(p_bad.encode())  + len(p_bad.encode()))  % 256
    ancien_bug = (sum_only_orig == sum_only_bad)
    fix_ok     = (sum_len_orig  != sum_len_bad)
    print('  ' + t + ':' + v + ':  sum_seul_identique=' + str(ancien_bug)
          + '  sum+len_different=' + str(fix_ok)
          + '  (ancien_xn=' + format(sum_only_orig, '02X')
          + ' vs ' + format(sum_only_bad, '02X') + ')'
          + '  (fix=' + format(sum_len_orig, '02X')
          + ' vs ' + format(sum_len_bad, '02X') + ')')
    chk('zero_inject_rejete ' + t + ':' + v, parse_msg(bad), None)

# ── 4. Demonstration faiblesse XOR ───────────────────────────────────────────
print()
print('[1.4] Faiblesse XOR — somme+len distingue les paires XOR-identiques')
def old_xor(s):
    r = 0
    for b in s.encode(): r ^= b
    return format(r, '02X')

pairs = [('H:AA', 'H:BB'), ('M:CC', 'M:DD'), ('S:001', 'S:100')]
for p1, p2 in pairs:
    x1, x2 = old_xor(p1), old_xor(p2)
    s1, s2 = calc_crc(p1), calc_crc(p2)
    print('  ' + repr(p1) + ': XOR=' + x1 + '  SumLen=' + s1)
    print('  ' + repr(p2) + ': XOR=' + x2 + '  SumLen=' + s2)
    xor_same   = (x1 == x2)
    sumlen_dif = (s1 != s2)
    print('  XOR identique=' + str(xor_same) + '  SumLen different=' + str(sumlen_dif))
    fake = p2 + ':' + x1   # forge avec signature XOR de p1
    chk('faux_paquet_xor ' + fake + ' rejete', parse_msg(fake), None)
    print()

# ── 5. Limite connue: byte-swap avec meme somme ───────────────────────────────
print('[1.5] Limite connue: byte-swap si meme somme (XOR et SumLen echouent tous les deux)')
swap_pairs = [('TL:EE:FF', 'TL:FF:EE'), ('M:AB', 'M:BA')]
for p1, p2 in swap_pairs:
    x1, x2 = old_xor(p1), old_xor(p2)
    s1, s2 = calc_crc(p1), calc_crc(p2)
    # Note: si len different -> sum+len peut distinguer
    len_diff = (len(p1) != len(p2))
    print('  ' + repr(p1) + ' XOR=' + x1 + ' SumLen=' + s1
          + '  vs  ' + repr(p2) + ' XOR=' + x2 + ' SumLen=' + s2
          + '  len_diff=' + str(len_diff))
    if s1 == s2:
        print('  -> Collision (limite connue pour paquets meme longueur + meme somme)')
    else:
        print('  -> SumLen distingue (longueurs differentes ou sommes differentes)')

# ── 6. Messages tronques ─────────────────────────────────────────────────────
print()
print('[1.6] Messages tronques / sans checksum')
for raw in ['H:1', 'M:0.500,0.500', 'H:', ':1:B6', 'AB', 'H:1:']:
    chk('tronque ' + repr(raw), parse_msg(raw), None)

# ── 7. Bruit pur ─────────────────────────────────────────────────────────────
print()
print('[1.7] Bruit pur / garbage / checksums invalides')
cs_h1 = calc_crc('H:1')
for raw in ['', '???', 'GARBAGE', ':::::', 'H:1:ZZ', 'H:1:00', 'H:1:b6']:
    chk('noise ' + repr(raw), parse_msg(raw), None)
# Le bon checksum majuscule doit passer
chk('H:1:' + cs_h1 + ' valide', parse_msg('H:1:' + cs_h1), ('H', '1'))
print('  Note: cs correct de H:1 = ' + cs_h1 + '  (b6 minuscules = rejete)')

# ── 8. Overflow 256 ──────────────────────────────────────────────────────────
print()
print('[1.8] Overflow modulo 256')
payload = 'M:' + 'Z' * 20
cs = calc_crc(payload)
d = payload.encode()
print('  sum(' + payload[:8] + '...Z*20) + len = '
      + str(sum(d)) + '+' + str(len(d)) + '=' + str(sum(d)+len(d))
      + ' -> %256=' + str((sum(d)+len(d)) % 256) + '=0x' + cs)
chk('overflow round-trip cs=' + cs, parse_msg(payload + ':' + cs), ('M', 'Z' * 20))
wrong = format((int(cs, 16) + 1) % 256, '02X')
chk('overflow wrong_cs=' + wrong + ' rejete', parse_msg(payload + ':' + wrong), None)

# ── 9. Compteur consecutifs ───────────────────────────────────────────────────
print()
print('[1.9] Compteur invalides consecutifs -> alerte au 3eme, reset sur valide')
inv = 0; alerts = 0; THRESHOLD = 3
cs_h1 = calc_crc('H:1')
seq = [
    ('H:1:00',          None,           'mauvais cs (devrait etre ' + cs_h1 + ')'),
    ('M:bad:ZZ',        None,           'cs non-hex'),
    ('GARBAGE:noise:99', None,          '3eme invalide -> alerte'),
    ('H:1:' + cs_h1,   ('H', '1'),     'valide -> reset'),
    ('H:1:00',          None,           'invalide -> inv=1'),
    ('H:1:' + cs_h1,   ('H', '1'),     'valide -> reset a 0'),
]
for raw, expected, note in seq:
    r = parse_msg(raw)
    if r is None:
        inv += 1
        if inv >= THRESHOLD: alerts += 1
    else:
        inv = 0
    print('  ' + repr(raw) + ' -> ' + ('REJETE' if r is None else 'ACCEPTE')
          + ' | inv=' + str(inv) + ' | alerts=' + str(alerts) + '  (' + note + ')')
chk('compteur reset apres valide', inv, 0)
chk('alerte au 3eme invalide', alerts >= 1, True)

# ── 10. Warnings logging ─────────────────────────────────────────────────────
print()
print('[1.10] Warnings logging generes:')
print('  ' + str(len(WARNS)) + ' warnings:')
for w in WARNS[:8]: print('    | ' + w)
if len(WARNS) > 8: print('    ... +' + str(len(WARNS) - 8) + ' autres')
chk('warnings generes', len(WARNS) > 0, True)

# ── Resume ────────────────────────────────────────────────────────────────────
print()
print('=' * 64)
print(' PHASE 1: ' + str(len(PASS)) + ' PASSES  ' + str(len(FAIL)) + ' ECHECS')
if FAIL:
    for f in FAIL: print('  !!! ECHEC: ' + f)
else:
    print(' Tous les tests passent — checksum (sum+len) mod 256 valide.')
print('=' * 64)
