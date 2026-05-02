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
#  Copyright (C) 2026 RickDnamps
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
# =============================================================================
# TEST DISPLAY RP2040 — ecran diagnostic seulement
# Ouvre dans Thonny et clique Run
# Ajuste RST_PIN: 12 = sans touch / 13 = avec touch
# =============================================================================

from machine import SPI, Pin
import gc9a01, time
import display as disp

RST_PIN = 12   # <-- change a 13 si modele avec touch
PAUSE   = 4    # secondes sur chaque ecran

# --- Init ---
time.sleep_ms(500)
Pin(25, Pin.OUT).value(1)
spi = SPI(1, baudrate=40_000_000, sck=Pin(10), mosi=Pin(11))
tft = gc9a01.GC9A01(spi, 240, 240,
    dc=Pin(8, Pin.OUT), cs=Pin(9, Pin.OUT),
    reset=Pin(RST_PIN, Pin.OUT), backlight=Pin(25, Pin.OUT))
tft.init()

items = {
    'UART':   'pending',
    'VESC_G': 'pending',
    'VESC_D': 'pending',
    'DOME':   'pending',
    'SERVOS': 'pending',
    'AUDIO':  'pending',
}

# 1 — Tous STANDBY (orange — etat au demarrage)
print("1/7 Tous STANDBY")
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE)

# 2 — Pi4B MASTER en cours de verification
print("2/7 Pi4B MASTER CHECKING")
items['UART'] = 'progress'
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE)

# 3 — Pi4B MASTER OK, AUDIO en cours
print("3/7 Pi4B MASTER OK / AUDIO CHECKING")
items['UART']  = 'ok'
items['AUDIO'] = 'progress'
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE)

# 4 — Phase 1 complete: UART + AUDIO OK, reste STANDBY
print("4/7 Phase 1 OK — VESC/DOME/SERVOS encore STANDBY")
items['AUDIO'] = 'ok'
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE)

# 5 — Tout OK (anneau vert)
print("5/7 Tout OK — anneau vert BOOT COMPLETE")
items['VESC_G'] = 'ok'
items['VESC_D'] = 'ok'
items['DOME']   = 'ok'
items['SERVOS'] = 'ok'
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE)

# 6 — VESC LEFT en erreur (anneau rouge)
print("6/7 VESC LEFT ERROR — anneau rouge")
items['VESC_G'] = 'fail'
disp.draw_boot_progress(tft, items)
time.sleep(PAUSE * 2)

# 7 — Pi4B MASTER hors ligne (le pire cas)
print("7/7 Pi4B MASTER OFFLINE — reste sur cet ecran")
items = {
    'UART':   'fail',
    'VESC_G': 'pending',
    'VESC_D': 'pending',
    'DOME':   'pending',
    'SERVOS': 'pending',
    'AUDIO':  'pending',
}
disp.draw_boot_progress(tft, items)

print("--- Test termine — ecran reste sur l'erreur ---")
