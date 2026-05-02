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
Display renderer — round GC9A01 240x240 screen.
"""

import gc9a01
import math

# RGB565 colors
BLACK      = gc9a01.color565(0,   0,   0)
WHITE      = gc9a01.color565(255, 255, 255)
RED        = gc9a01.color565(220, 50,  50)
GREEN      = gc9a01.color565(50,  200, 80)
ORANGE     = gc9a01.color565(255, 150, 0)
ORANGE_MED = gc9a01.color565(180, 90,  0)   # comet mid
ORANGE_DIM = gc9a01.color565(90,  45,  0)   # comet tail
BLUE       = gc9a01.color565(0,   120, 220)
GRAY       = gc9a01.color565(80,  80,  80)
DK_GRAY    = gc9a01.color565(40,  40,  40)
CYAN       = gc9a01.color565(0,   200, 200)

CENTER_X = 120
CENTER_Y = 120

_spin_frame = 0   # animation frame counter

# russhughes fonts
try:
    import vga1_8x16 as _font16
except ImportError:
    _font16 = None

try:
    import vga1_8x8 as _font8
except ImportError:
    _font8 = None

_font = _font8 if _font8 is not None else _font16

ERROR_MESSAGES = {
    'MASTER_OFFLINE': ('Master',   'offline'),
    'VESC_TEMP_HIGH': ('VESC',     'overheat!'),
    'VESC_FAULT':     ('VESC',     'fault'),
    'BATTERY_LOW':    ('Battery',  'low!'),
    'UART_ERROR':     ('UART',     'error'),
    'SYNC_FAILED':    ('Sync',     'failed'),
    'WATCHDOG':       ('Watchdog', 'triggered'),
    'AUDIO_FAIL':     ('Audio',    'error'),
    'SERVO_FAIL':     ('Servos',   'error'),
    'VESC_L_FAIL':    ('VESC L',   'error'),
    'VESC_R_FAIL':    ('VESC R',   'error'),
    'I2C_ERROR':      ('I2C',      'error'),
}

BOOT_LABELS = {
    'UART':    'Pi4B MASTER',
    'VESC_G':  'VESC LEFT',
    'VESC_D':  'VESC RIGHT',
    'DOME':    'DOME MOTOR',
    'SERVOS':  'SERVOS BODY',
    'AUDIO':   'AUDIO',
    'BT_CTRL': 'BT CONTROL',
}

STATUS_TEXT = {
    'pending':  'STANDBY',
    'progress': 'CHECKING',
    'ok':       'OK',
    'fail':     'ERROR',
    'none':     'NO CTRL',
}

STATUS_COLOR = {
    'pending':  GRAY,
    'progress': ORANGE,
    'ok':       GREEN,
    'fail':     RED,
    'none':     BLUE,
}

# ------------------------------------------------------------------
# Pre-computed BOOTING animated circle — 12 comet dots
# ------------------------------------------------------------------
_N_TICKS   = 12
_TICK_R    = 75   # radius of the dots on the circle
_TICK_SIZE = 8    # size of each dot (square)

# Comet colors: head -> tail (the last DK_GRAY erases the tail)
_ARC_COLORS = [ORANGE, ORANGE_MED, ORANGE_DIM, DK_GRAY]

_TICKS = []
for _i in range(_N_TICKS):
    _a = -math.pi / 2 + _i * 2 * math.pi / _N_TICKS   # start top, clockwise
    _TICKS.append((
        int(CENTER_X + _TICK_R * math.cos(_a)) - _TICK_SIZE // 2,
        int(CENTER_Y + _TICK_R * math.sin(_a)) - _TICK_SIZE // 2,
        _TICK_SIZE, _TICK_SIZE,
    ))

# Flags to avoid full-redraw on every animation frame
_booting_bg_drawn  = False
_locked_bg_drawn   = False
_ok_bg_drawn       = False   # safety: forces full redraw if screen cleared by another state
_ok_prev_bus_color = None    # color tracking for incremental draw_ok()


def reset_animations():
    """Call when leaving an animated state to force a full redraw on return.
    Must be called by all screens that call tft.fill(BLACK), except draw_ok itself."""
    global _booting_bg_drawn, _locked_bg_drawn, _ok_bg_drawn
    _booting_bg_drawn = False
    _locked_bg_drawn  = False
    _ok_bg_drawn      = False   # the OK screen will need to be fully redrawn


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _text(tft, txt, x, y, color, font=None):
    f = font if font is not None else _font
    if f is not None:
        try:
            tft.text(f, txt, x, y, color)
        except Exception:
            pass


def _text_center(tft, txt, y, color, font=None):
    f = font if font is not None else _font
    if f is None:
        return
    x = CENTER_X - (len(txt) * 8) // 2
    _text(tft, txt, x, y, color, f)


def _draw_ring(tft, cx, cy, r, thickness, color):
    """Ring via fill_rect — uses isqrt to avoid math.sqrt."""
    r_inner = r - thickness
    r2_outer = r * r
    r2_inner = r_inner * r_inner
    for dy in range(-r, r + 1):
        d2 = dy * dy
        ro2 = r2_outer - d2
        if ro2 < 0:
            continue
        dx_outer = int(math.sqrt(ro2))
        ri2 = r2_inner - d2
        dx_inner = int(math.sqrt(ri2)) if ri2 >= 0 else 0
        w = dx_outer - dx_inner
        if w > 0:
            tft.fill_rect(cx - dx_outer, cy + dy, w, 1, color)
            tft.fill_rect(cx + dx_inner, cy + dy, w, 1, color)


def _progress_bar(tft, x, y, w, h, pct, color):
    tft.fill_rect(x, y, w, h, DK_GRAY)
    filled = int(w * max(0.0, min(1.0, pct)))
    if filled > 0:
        tft.fill_rect(x, y, filled, h, color)
    tft.fill_rect(x,         y,         w, 1, GRAY)
    tft.fill_rect(x,         y + h - 1, w, 1, GRAY)
    tft.fill_rect(x,         y,         1, h, GRAY)
    tft.fill_rect(x + w - 1, y,         1, h, GRAY)


# ------------------------------------------------------------------
# Screens
# ------------------------------------------------------------------

def draw_booting(tft, full=False):
    """Animated orange circle (12-dot comet) — full=True forces complete redraw."""
    global _spin_frame, _booting_bg_drawn
    _spin_frame = (_spin_frame + 1) % _N_TICKS

    if full or not _booting_bg_drawn:
        tft.fill(BLACK)
        _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, ORANGE)
        _text_center(tft, 'R2-D2',       CENTER_Y - 12, ORANGE)
        _text_center(tft, 'STARTING UP', CENTER_Y + 4,  WHITE)
        for tx, ty, tw, th in _TICKS:
            tft.fill_rect(tx, ty, tw, th, DK_GRAY)
        _booting_bg_drawn = True

    # Incremental update — 4 fill_rect per frame
    # The last _ARC_COLORS entry is DK_GRAY => automatically erases the tail
    for i, col in enumerate(_ARC_COLORS):
        tx, ty, tw, th = _TICKS[(_spin_frame - i) % _N_TICKS]
        tft.fill_rect(tx, ty, tw, th, col)


def draw_locked(tft, full=False):
    """Blinking red padlock — full=True forces complete redraw."""
    global _spin_frame, _locked_bg_drawn
    _spin_frame = (_spin_frame + 1) % 4
    visible     = _spin_frame < 2
    ring_color  = RED if visible else DK_GRAY

    if full or not _locked_bg_drawn:
        tft.fill(BLACK)
        reset_animations()   # the OK screen will need full redraw on next return
        _text_center(tft, 'SYSTEM STATUS:', 36, RED)
        # Padlock body
        tft.fill_rect(CENTER_X - 20, CENTER_Y - 8, 40, 30, RED)
        tft.fill_rect(CENTER_X - 13, CENTER_Y - 2, 26, 18, BLACK)
        # Keyhole
        tft.fill_rect(CENTER_X - 3, CENTER_Y + 2, 7, 10, RED)
        # Shackle
        arc_r = 16
        for dy in range(-arc_r, 0):
            r2 = arc_r * arc_r - dy * dy
            if r2 >= 0:
                tft.fill_rect(CENTER_X - 22, CENTER_Y - 8 + dy, 5, 1, RED)
                tft.fill_rect(CENTER_X + 17, CENTER_Y - 8 + dy, 5, 1, RED)
        _text_center(tft, 'SYSTEM',             CENTER_Y + 28, RED)
        _text_center(tft, 'LOCKED',             CENTER_Y + 40, RED)
        tft.fill_rect(CENTER_X - 50, CENTER_Y + 54, 100, 1, DK_GRAY)
        _text_center(tft, 'WATCHDOG TRIGGERED', CENTER_Y + 60, GRAY)
        _text_center(tft, 'MOTORS STOPPED',     CENTER_Y + 72, GRAY)
        _locked_bg_drawn = True

    # Only the ring blinks — incremental update
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, ring_color)


def draw_ok(tft, version, bus_pct=100.0, full=False):
    """Full redraw if full=True or _ok_bg_drawn=False, otherwise incremental (bus update).
    Do NOT call reset_animations() here — that is the role of the other screens."""
    global _ok_prev_bus_color, _ok_bg_drawn
    bus_color     = GREEN if bus_pct >= 80.0 else ORANGE
    color_changed = (bus_color != _ok_prev_bus_color)
    _ok_prev_bus_color = bus_color

    if full or not _ok_bg_drawn:
        # Full redraw — state change OR safety if screen cleared by another state
        tft.fill(BLACK)
        _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, bus_color)
        _text_center(tft, 'SYSTEM STATUS:', 50, GREEN)
        _text_center(tft, 'OPERATIONAL',   64, GREEN)
        tft.fill_rect(CENTER_X - 50, 78, 100, 1, DK_GRAY)
        if version:
            _text_center(tft, 'v' + version[:11], 88, GREEN)
        _text_center(tft, 'UART BUS HEALTH', 106, bus_color)
        tft.fill_rect(CENTER_X - 50, 156, 100, 1, DK_GRAY)
        _text_center(tft, '< swipe >  TELEM', 164, GRAY)
        _ok_bg_drawn = True
    elif color_changed:
        # Color crosses the 80% threshold: redraw ring + label only
        _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, bus_color)
        # Clear only the width of "UART BUS HEALTH" text (15c×8=120px, cx=120)
        tft.fill_rect(56, 106, 128, 9, BLACK)
        _text_center(tft, 'UART BUS HEALTH', 106, bus_color)

    # Dynamic parts: always updated without clearing the whole screen
    _progress_bar(tft, 34, 118, 172, 10, bus_pct / 100.0, bus_color)
    tft.fill_rect(CENTER_X - 24, 133, 48, 9, BLACK)
    _text_center(tft, '{:.0f}%'.format(bus_pct), 133, bus_color)
    if bus_pct < 80.0:
        _text_center(tft, 'INTERFERENCE DETECTED', 147, ORANGE)
    elif not full:
        # Clear only the width of "INTERFERENCE DETECTED" text (18c×8=144px, cx=120)
        tft.fill_rect(44, 147, 152, 9, BLACK)
    # NOTE: NO reset_animations() here — draw_ok must not reset the other screens' flags


def _draw_antenna(tft, cx, cy, color):
    """Antenna with 3 waves — drawn with primitives."""
    # Vertical mast
    tft.fill_rect(cx - 1, cy - 28, 3, 28, color)
    # 3 wave arcs (approximated by horizontal circle arcs)
    for r, dy_offset in [(10, -28), (17, -32), (24, -36)]:
        for dy in range(-r // 3, r // 3 + 1):
            dx = int((r * r - dy * dy * 9) ** 0.5) if r * r >= dy * dy * 9 else 0
            if dx > 0:
                tft.fill_rect(cx - dx, cy + dy_offset + r // 3 + dy, dx * 2, 1, color)
                break
        # Simpler approach: just staggered horizontal bars
    tft.fill_rect(cx -  8, cy - 22, 16, 2, color)
    tft.fill_rect(cx - 14, cy - 28, 28, 2, color)
    tft.fill_rect(cx - 20, cy - 34, 40, 2, color)
    # Base point
    tft.fill_rect(cx - 3, cy, 7, 3, color)


def draw_net(tft, sub_state):
    tft.fill(BLACK)
    reset_animations()   # the OK screen will need full redraw on next return
    parts = sub_state.split(':') if sub_state else []
    cmd   = parts[0].upper() if parts else ''
    # Color by state: ORANGE for HOME FALLBACK (degraded mode), BLUE for normal reconnection
    if cmd in ('HOME_TRY', 'HOME'):
        net_color = ORANGE
        ring_w    = 5
    elif cmd == 'OK':
        net_color = GREEN
        ring_w    = 5
    else:   # SCANNING, AP, other
        net_color = BLUE
        ring_w    = 6
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, ring_w, net_color)
    _text_center(tft, 'NETWORK', 36, net_color)
    _draw_antenna(tft, CENTER_X, CENTER_Y + 10, net_color)
    if cmd == 'SCANNING':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'SCANNING...',              CENTER_Y + 46, net_color)
        _text_center(tft, 'MASTER AP NOT FOUND',      CENTER_Y + 58, GRAY)
        _text_center(tft, 'ATTEMPT {}/5'.format(n),   CENTER_Y + 70, GRAY)
    elif cmd == 'AP':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'CONNECTING',               CENTER_Y + 46, net_color)
        _text_center(tft, 'AstromechOS',             CENTER_Y + 58, net_color)
        _text_center(tft, 'ATTEMPT {}/5'.format(n),   CENTER_Y + 70, GRAY)
    elif cmd == 'HOME_TRY':
        _text_center(tft, 'HOME WIFI',                CENTER_Y + 46, ORANGE)
        _text_center(tft, 'CONNECTING...',            CENTER_Y + 58, GRAY)
    elif cmd == 'HOME':
        ip = ':'.join(parts[1:]) if len(parts) > 1 else '?'
        _text_center(tft, 'HOME WIFI ACTIVE',         CENTER_Y + 46, ORANGE)
        _text_center(tft, ip[:16],                    CENTER_Y + 58, GRAY)
        _text_center(tft, 'SSH DEBUG OK',             CENTER_Y + 70, GRAY)
    elif cmd == 'OK':
        _text_center(tft, 'RECONNECTED',              CENTER_Y + 46, GREEN)
    else:
        _text_center(tft, sub_state[:16] if sub_state else 'NET EVENT', CENTER_Y + 46, net_color)


def draw_error(tft, code):
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, RED)
    _text_center(tft, 'SYSTEM STATUS:', 40, RED)
    _text_center(tft, 'CRITICAL ERROR', 52, RED)
    tft.fill_rect(CENTER_X - 6, CENTER_Y - 50, 12, 30, RED)
    tft.fill_rect(CENTER_X - 6, CENTER_Y - 12, 12, 12, RED)
    msg = ERROR_MESSAGES.get(code, ('Error', code[:10]))
    _text_center(tft, msg[0], CENTER_Y + 20, RED)
    _text_center(tft, msg[1], CENTER_Y + 32, WHITE)
    _text_center(tft, 'GLOBAL STATUS:', CENTER_Y + 50, GRAY)
    _text_center(tft, 'BOOT FAILED',   CENTER_Y + 62, RED)
    reset_animations()


def draw_telemetry(tft, voltage, temp):
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, BLUE)
    _text_center(tft, 'TELEMETRY', 34, BLUE)
    # Voltage
    v_str     = '{:.1f}V'.format(voltage)
    _text_center(tft, v_str, 52, WHITE)
    v_pct     = max(0.0, min(1.0, (voltage - 20.0) / 9.4))
    bar_color = GREEN if v_pct > 0.3 else (ORANGE if v_pct > 0.15 else RED)
    _progress_bar(tft, 34, 66, 172, 14, v_pct, bar_color)
    lipo_pct  = '{:.0f}%'.format(v_pct * 100)
    _text_center(tft, '6S LiPo  ' + lipo_pct, 85, bar_color)
    tft.fill_rect(CENTER_X - 50, 98, 100, 1, DK_GRAY)
    # Temperature
    temp_color = GREEN if temp < 60 else (ORANGE if temp < 75 else RED)
    t_str      = 'TEMP: {:.0f}C'.format(temp)
    _text_center(tft, t_str, 108, temp_color)
    _progress_bar(tft, 34, 122, 172, 10, temp / 100.0, temp_color)
    tft.fill_rect(CENTER_X - 50, 142, 100, 1, DK_GRAY)
    _text_center(tft, '< swipe  BACK TO OK', 150, GRAY)
    reset_animations()


def draw_boot(tft):
    """Legacy initial splash screen."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 6, ORANGE)
    tft.fill_rect(CENTER_X - 55, CENTER_Y - 75, 110, 60, WHITE)
    tft.fill_rect(CENTER_X - 45, CENTER_Y - 65, 90,  45, BLACK)
    tft.fill_rect(CENTER_X - 35, CENTER_Y - 5,  70,  50, WHITE)
    tft.fill_rect(CENTER_X - 27, CENTER_Y + 3,  54,  34, BLACK)
    _text_center(tft, 'R2-D2',   CENTER_Y + 60, ORANGE)
    _text_center(tft, 'BOOT...', CENTER_Y + 72, GRAY)
    reset_animations()
