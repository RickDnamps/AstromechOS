"""
Display renderer — ecran rond GC9A01 240x240.
"""

import gc9a01
import math

# Couleurs RGB565
BLACK   = gc9a01.color565(0,   0,   0)
WHITE   = gc9a01.color565(255, 255, 255)
RED     = gc9a01.color565(220, 50,  50)
GREEN   = gc9a01.color565(50,  200, 80)
ORANGE  = gc9a01.color565(255, 150, 0)
BLUE    = gc9a01.color565(0,   120, 220)
GRAY    = gc9a01.color565(80,  80,  80)
DK_GRAY = gc9a01.color565(40,  40,  40)
CYAN    = gc9a01.color565(0,   200, 200)

CENTER_X = 120
CENTER_Y = 120

_spin_frame = 0   # animation frame counter — incremented each draw call

# Fontes russhughes — 8x8 pour diagnostic (plus de lignes), 8x16 pour grands titres
try:
    import vga1_8x16 as _font16
except ImportError:
    _font16 = None

try:
    import vga1_8x8 as _font8
except ImportError:
    _font8 = None

# Police par defaut pour les petits textes
_font = _font8 if _font8 is not None else _font16

# Messages d'erreur lisibles
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

# Labels courts des items de boot (max ~11 chars pour tenir sur 1 ligne)
# Ordre = ordre d'affichage sur l'ecran
BOOT_LABELS = {
    'UART':    'Pi4B MASTER',   # UART /dev/ttyAMA0 slipring → Master (CRITICAL)
    'VESC_G':  'VESC LEFT',     # FSESC /dev/ttyACM0 — left drive
    'VESC_D':  'VESC RIGHT',    # FSESC /dev/ttyACM1 — right drive
    'DOME':    'DOME MOTOR',    # Motor Driver HAT I2C 0x40 — dome rotation
    'SERVOS':  'SERVOS BODY',   # PCA9685 I2C 0x41 — panels + arms
    'AUDIO':   'AUDIO',         # 3.5mm jack — MP3 sounds
    'BT_CTRL': 'BT CONTROL',    # Bluetooth controller (optional)
}

# Textes de statut par etat
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


def _text(tft, txt, x, y, color, font=None):
    """Texte — requiert font module russhughes."""
    f = font if font is not None else _font
    if f is not None:
        try:
            tft.text(f, txt, x, y, color)
        except Exception:
            pass


def _text_center(tft, txt, y, color, font=None):
    """Texte centre horizontalement."""
    f = font if font is not None else _font
    if f is None:
        return
    # vga1_8x8 → 8px par char, vga1_8x16 → 8px par char aussi
    char_w = 8
    x = CENTER_X - (len(txt) * char_w) // 2
    _text(tft, txt, x, y, color, f)


def _draw_ring(tft, cx, cy, r, thickness, color):
    """Anneau (bordure circulaire) via fill_rect."""
    r_inner = r - thickness
    for dy in range(-r, r + 1):
        r2 = r * r - dy * dy
        if r2 < 0:
            continue
        dx_outer = int(math.sqrt(r2))
        r2i = r_inner * r_inner - dy * dy
        dx_inner = int(math.sqrt(r2i)) if r2i >= 0 else 0
        if dx_outer > dx_inner:
            tft.fill_rect(cx - dx_outer, cy + dy, dx_outer - dx_inner, 1, color)
            tft.fill_rect(cx + dx_inner, cy + dy, dx_outer - dx_inner, 1, color)


def _progress_bar(tft, x, y, w, h, pct, color):
    """Barre de progression avec fond gris."""
    tft.fill_rect(x, y, w, h, DK_GRAY)
    filled = int(w * max(0.0, min(1.0, pct)))
    if filled > 0:
        tft.fill_rect(x, y, filled, h, color)
    # Contour
    tft.fill_rect(x,         y,         w, 1, GRAY)
    tft.fill_rect(x,         y + h - 1, w, 1, GRAY)
    tft.fill_rect(x,         y,         1, h, GRAY)
    tft.fill_rect(x + w - 1, y,         1, h, GRAY)


# ------------------------------------------------------------------
# Ecrans
# ------------------------------------------------------------------

def draw_boot(tft):
    """Splash initial — logo R2-D2 + bordure orange."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 6, ORANGE)
    # Dome
    tft.fill_rect(CENTER_X - 55, CENTER_Y - 75, 110, 60, WHITE)
    tft.fill_rect(CENTER_X - 45, CENTER_Y - 65, 90,  45, BLACK)
    # Corps
    tft.fill_rect(CENTER_X - 35, CENTER_Y - 5,  70,  50, WHITE)
    tft.fill_rect(CENTER_X - 27, CENTER_Y + 3,  54,  34, BLACK)
    _text_center(tft, 'R2-D2',   CENTER_Y + 60, ORANGE)
    _text_center(tft, 'BOOT...', CENTER_Y + 72, GRAY)


def draw_booting(tft):
    """Ecran de demarrage — spinner orange. Remplace le suivi individuel des items."""
    global _spin_frame
    _spin_frame = (_spin_frame + 1) % 8

    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 6, ORANGE)
    _text_center(tft, 'STARTING UP', CENTER_Y - 20, ORANGE)
    _text_center(tft, 'Please wait', CENTER_Y - 6,  GRAY)

    # Spinner : 8 segments rayonnants, segment actif = ORANGE
    sr = 28
    seg_len = 12
    for i in range(8):
        rad = i * math.pi / 4.0
        x1 = int(CENTER_X + math.cos(rad) * sr)
        y1 = int(CENTER_Y + math.sin(rad) * sr)
        x2 = int(CENTER_X + math.cos(rad) * (sr + seg_len))
        y2 = int(CENTER_Y + math.sin(rad) * (sr + seg_len))
        color = ORANGE if i == _spin_frame else DK_GRAY
        tft.fill_rect(min(x1, x2), min(y1, y2),
                      max(2, abs(x2 - x1)), max(2, abs(y2 - y1)), color)

    _text_center(tft, 'R2-D2', CENTER_Y + 50, ORANGE)


def draw_boot_progress(tft, items):
    """
    Ecran de diagnostic boot — style reference image.
    Affiche: titre SYSTEM STATUS + etat, liste numerotee des items,
    barre de progression, pied GLOBAL STATUS.
    """
    # Determiner l'etat global
    statuses = list(items.values())
    has_fail     = any(s == 'fail'           for s in statuses)
    has_progress = any(s == 'progress'       for s in statuses)
    all_done     = all(s in ('ok', 'none')   for s in statuses)

    if has_fail:
        ring_color  = RED
        state_line  = 'BOOT ERROR'
        global_text = 'BOOT FAILED'
    elif all_done:
        ring_color  = GREEN
        state_line  = 'OK'
        global_text = 'BOOT COMPLETE'
    else:
        ring_color  = ORANGE
        state_line  = 'IN PROGRESS'
        global_text = 'BOOTING...'

    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, ring_color)

    # --- Titre ---
    # y=32 : inner ring width = 2*sqrt(107^2-88^2) = 122px — "SYSTEM STATUS:"(112px) fits
    # y=44 : inner ring width = 150px — state line fits
    _text_center(tft, 'SYSTEM STATUS:', 32, ring_color)
    _text_center(tft, state_line,       44, ring_color)

    # --- Liste des items ---
    # y=60..115 : inner ring width >= 168px
    # x=32, 22 chars * 8px = 176px → x: 32..208 (inner edge at ~31..209 at y=60)
    # Format: "N.LABEL(11)..STATUS" cible 22 chars
    ok_count = 0
    y = 60
    for i, (key, label) in enumerate(BOOT_LABELS.items()):
        status = items.get(key, 'pending')
        if status in ('ok', 'none'):
            ok_count += 1
        color      = STATUS_COLOR.get(status, GRAY)
        status_str = STATUS_TEXT.get(status, status)

        num_str   = '{}.'.format(i + 1)
        short     = label[:11].upper()
        left      = '{}{}'.format(num_str, short)
        dot_count = max(1, 22 - len(left) - len(status_str))
        line      = '{}{}{}'.format(left, '.' * dot_count, status_str)

        _text(tft, line, 32, y, color)
        y += 10  # 8px font + 2px gap (7 items, tighter spacing)

    # --- Barre de progression ---
    # y=123 : largement dans la zone centrale du cercle
    pct   = ok_count / max(1, len(items))
    bar_y = y + 4
    _progress_bar(tft, 32, bar_y, 176, 9, pct, ring_color)

    # --- Pied de page ---
    _text_center(tft, 'GLOBAL STATUS:', bar_y + 13, GRAY)
    _text_center(tft, global_text,      bar_y + 23, ring_color)


def draw_operational(tft, version):
    """Ecran 'tout OK' vert — affiche 3s puis transition automatique vers draw_ok."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, GREEN)
    _text_center(tft, 'SYSTEM STATUS:', 50, GREEN)
    _text_center(tft, 'OK',            62, GREEN)
    # Gros checkmark simple
    tft.fill_rect(CENTER_X - 38, CENTER_Y - 10, 76, 12, GREEN)
    tft.fill_rect(CENTER_X - 38, CENTER_Y + 2,  76, 12, GREEN)
    _text_center(tft, 'OPERATIONAL', CENTER_Y + 28, GREEN)
    if version:
        _text_center(tft, version[:14], CENTER_Y + 42, GRAY)


def draw_ok(tft, version, bus_pct=100.0):
    """Ecran operationnel normal — bordure verte fine + barre bus health."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, GREEN)
    _text_center(tft, 'SYSTEM STATUS:', 42, GREEN)
    _text_center(tft, 'OK',            54, GREEN)
    tft.fill_rect(CENTER_X - 40, CENTER_Y - 14, 80, 12, GREEN)
    tft.fill_rect(CENTER_X - 40, CENTER_Y +  2, 80, 12, GREEN)
    _text_center(tft, 'READY', CENTER_Y + 24, GREEN)
    if version:
        _text_center(tft, version[:14], CENTER_Y + 38, GRAY)
    # Barre bus health
    bus_color = GREEN if bus_pct >= 80.0 else ORANGE
    bus_label = 'BUS {:.0f}%'.format(bus_pct)
    _text_center(tft, bus_label, CENTER_Y + 54, bus_color)
    _progress_bar(tft, 34, CENTER_Y + 64, 172, 8, bus_pct / 100.0, bus_color)


def draw_net(tft, sub_state):
    """Ecran reseau — antenne + sous-etat (SCANNING:N, AP:N, HOME_TRY, HOME:<ip>, OK)."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 5, CYAN)
    _text_center(tft, 'WIFI', 30, CYAN)

    # Antenne simple : 3 barres horizontales etagees
    cx, cy = CENTER_X, CENTER_Y + 10
    for radius, alpha in [(14, 255), (24, 180), (34, 100)]:
        c = gc9a01.color565(0, alpha, alpha)
        tft.fill_rect(cx - radius, cy - radius, radius * 2, 3, c)
    # Mat de l'antenne
    tft.fill_rect(cx - 1, cy - 34, 3, 34, CYAN)
    tft.fill_rect(cx - 8, cy,      17,  3, CYAN)

    # Sous-etat
    parts = sub_state.split(':') if sub_state else []
    cmd = parts[0].upper() if parts else ''

    if cmd == 'SCANNING':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'SCANNING...',                   CENTER_Y + 46, CYAN)
        _text_center(tft, 'Attempt {}/{}'.format(n, 5),   CENTER_Y + 58, GRAY)
    elif cmd == 'AP':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'CONNECTING AP',                 CENTER_Y + 46, CYAN)
        _text_center(tft, 'Attempt {}/{}'.format(n, 5),   CENTER_Y + 58, GRAY)
    elif cmd == 'HOME_TRY':
        _text_center(tft, 'HOME WIFI',                     CENTER_Y + 46, ORANGE)
        _text_center(tft, 'Connecting...',                 CENTER_Y + 58, GRAY)
    elif cmd == 'HOME':
        ip = ':'.join(parts[1:]) if len(parts) > 1 else '?'
        _text_center(tft, 'HOME WIFI',                     CENTER_Y + 46, ORANGE)
        _text_center(tft, ip[:16],                         CENTER_Y + 58, GRAY)
    elif cmd == 'OK':
        _text_center(tft, 'RECONNECTED',                   CENTER_Y + 46, GREEN)
    else:
        _text_center(tft, sub_state[:16] if sub_state else 'NET EVENT', CENTER_Y + 46, CYAN)


def draw_locked(tft):
    """Cadenas rouge — watchdog VESC declenche. Anneau clignotant via _spin_frame."""
    global _spin_frame
    _spin_frame = (_spin_frame + 1) % 4
    visible = _spin_frame < 2  # clignote ON/OFF 50%

    tft.fill(BLACK)
    ring_color = RED if visible else DK_GRAY
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, ring_color)
    _text_center(tft, 'SYSTEM STATUS:', 34, RED)
    _text_center(tft, 'LOCKED',        46, RED)

    # Corps du cadenas
    tft.fill_rect(CENTER_X - 20, CENTER_Y - 10, 40, 32, RED)
    tft.fill_rect(CENTER_X - 14, CENTER_Y - 4,  28, 20, BLACK)
    # Anse du cadenas
    arc_r = 16
    for dy in range(-arc_r, 0):
        r2 = arc_r * arc_r - dy * dy
        if r2 >= 0:
            tft.fill_rect(CENTER_X - 21, CENTER_Y - 10 + dy, 4, 1, RED)
            tft.fill_rect(CENTER_X + 17, CENTER_Y - 10 + dy, 4, 1, RED)

    _text_center(tft, 'WATCHDOG',      CENTER_Y + 36, RED)
    _text_center(tft, 'TRIGGERED',     CENTER_Y + 48, WHITE)


def draw_error(tft, code):
    """Ecran erreur — bordure rouge epaisse + description lisible."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, RED)
    _text_center(tft, 'SYSTEM STATUS:', 40, RED)
    _text_center(tft, 'CRITICAL ERROR', 52, RED)
    # Exclamation mark
    tft.fill_rect(CENTER_X - 6, CENTER_Y - 50, 12, 30, RED)
    tft.fill_rect(CENTER_X - 6, CENTER_Y - 12, 12, 12, RED)
    # Human-readable message
    msg = ERROR_MESSAGES.get(code, ('Error', code[:10]))
    _text_center(tft, msg[0], CENTER_Y + 20, RED)
    _text_center(tft, msg[1], CENTER_Y + 32, WHITE)
    _text_center(tft, 'GLOBAL STATUS:', CENTER_Y + 50, GRAY)
    _text_center(tft, 'BOOT FAILED',   CENTER_Y + 62, RED)


def draw_telemetry(tft, voltage, temp):
    """Jauge batterie + temperature — bordure bleue."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, BLUE)
    _text_center(tft, 'TELEMETRY', 28, BLUE)
    # Tension
    v_str = '{:.1f}V'.format(voltage)
    _text_center(tft, v_str, 48, WHITE)
    # Jauge batterie (20V-29.4V = 0-100%)
    v_pct = max(0.0, min(1.0, (voltage - 20.0) / 9.4))
    bar_color = GREEN if v_pct > 0.3 else (ORANGE if v_pct > 0.15 else RED)
    _progress_bar(tft, 34, 70, 172, 16, v_pct, bar_color)
    # Temperature
    temp_color = GREEN if temp < 60 else (ORANGE if temp < 75 else RED)
    t_str = 'TEMP: {:.0f}C'.format(temp)
    _text_center(tft, t_str, 100, temp_color)
    # Temp bar (0-100C)
    _progress_bar(tft, 34, 116, 172, 10, temp / 100.0, temp_color)
