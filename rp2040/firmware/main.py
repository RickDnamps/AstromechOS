"""
R2-D2 RP2040 Firmware — MicroPython.
Waveshare RP2040-LCD-1.28 / RP2040-Touch-LCD-1.28 (GC9A01).
"""

import gc9a01
import time
from machine import SPI, Pin
import display as disp

time.sleep_ms(500)  # laisser le hardware se stabiliser au boot

Pin(25, Pin.OUT).value(1)  # backlight ON
spi = SPI(1, baudrate=40_000_000, sck=Pin(10), mosi=Pin(11))
tft = gc9a01.GC9A01(spi, 240, 240,
    dc=Pin(8,  Pin.OUT),
    cs=Pin(9,  Pin.OUT),
    reset=Pin(12, Pin.OUT),   # 12 = sans touch / 13 = avec touch
    backlight=Pin(25, Pin.OUT))
tft.init()

disp.draw_boot(tft)

while True:
    time.sleep_ms(500)
