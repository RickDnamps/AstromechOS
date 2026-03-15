"""
Touch handler — CST816S capacitif sur bus I2C.
Gestures: TAP, SWIPE (4 directions), HOLD (2s), DOUBLE_TAP.
"""

import time
from machine import I2C

CST816S_ADDR    = 0x15
REG_GESTURE     = 0x01
REG_FINGER      = 0x02
REG_XPOS_H      = 0x03
REG_XPOS_L      = 0x04
REG_YPOS_H      = 0x05
REG_YPOS_L      = 0x06

# Codes gestes renvoyés par le CST816S
GESTURE_NONE        = 0x00
GESTURE_SWIPE_UP    = 0x01
GESTURE_SWIPE_DOWN  = 0x02
GESTURE_SWIPE_LEFT  = 0x03
GESTURE_SWIPE_RIGHT = 0x04
GESTURE_SINGLE_TAP  = 0x05
GESTURE_DOUBLE_TAP  = 0x0B
GESTURE_LONG_PRESS  = 0x0C

HOLD_THRESHOLD_MS = 2000


class TouchHandler:
    def __init__(self, i2c: I2C):
        self._i2c = i2c
        self._callbacks = {
            'tap':        [],
            'double_tap': [],
            'hold':       [],
            'swipe_up':   [],
            'swipe_down': [],
            'swipe_left': [],
            'swipe_right':[],
        }

    def on(self, event: str, callback) -> None:
        """Enregistre un callback pour un événement tactile."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def poll(self) -> None:
        """À appeler régulièrement dans la boucle principale."""
        try:
            data = self._i2c.readfrom_mem(CST816S_ADDR, REG_GESTURE, 6)
        except OSError:
            return

        gesture = data[0]
        fingers = data[1]
        if fingers == 0 and gesture == GESTURE_NONE:
            return

        x = ((data[2] & 0x0F) << 8) | data[3]
        y = ((data[4] & 0x0F) << 8) | data[5]

        event = self._gesture_to_event(gesture)
        if event:
            self._fire(event, x, y)

    def _gesture_to_event(self, gesture: int) -> str | None:
        mapping = {
            GESTURE_SINGLE_TAP:  'tap',
            GESTURE_DOUBLE_TAP:  'double_tap',
            GESTURE_LONG_PRESS:  'hold',
            GESTURE_SWIPE_UP:    'swipe_up',
            GESTURE_SWIPE_DOWN:  'swipe_down',
            GESTURE_SWIPE_LEFT:  'swipe_left',
            GESTURE_SWIPE_RIGHT: 'swipe_right',
        }
        return mapping.get(gesture)

    def _fire(self, event: str, x: int, y: int) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(x, y)
            except Exception as e:
                print(f"Touch callback erreur {event}: {e}")
