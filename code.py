# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# feather-tft-gamepad
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
# - Adafruit USB Host FeatherWing with MAX3421E (#5858)
# - 8BitDo SN30 Pro USB gamepad
#
# Pinouts:
# | TFT feather | USB Host | ST7789 TFT |
# | ----------- | -------- | ---------- |
# |  SCK        |  SCK     |            |
# |  MOSI       |  MOSI    |            |
# |  MISO       |  MISO    |            |
# |  D9         |  IRQ     |            |
# |  D10        |  CS      |            |
# |  TFT_CS     |          |  CS        |
# |  TFT_DC     |          |  DC        |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e
#
from board import D9, D10, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import (Bitmap, Group, OnDiskBitmap, Palette, TileGrid,
    release_displays)
from fourwire import FourWire
import gc
from max3421e import Max3421E
from time import sleep
from usb.core import USBError

from adafruit_st7789 import ST7789
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, L, R, A, B, X, Y)


def update_GUI(buttons):
    # TODO: update TileGrid sprites
    print(f"{buttons:016b}")

def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize display
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()
    bmp = OnDiskBitmap(open("sprites.bmp", "rb"))
    tiles = TileGrid(bmp, pixel_shader=bmp.pixel_shader)
    grp = Group(scale=3)
    grp.append(tiles)
    display.root_group = grp
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    gp = XInputGamepad()
    print("Looking for USB gamepad...")
    while True:
        gc.collect()
        try:
            if gp.find_and_configure(retries=25):
                # Found a gamepad, so configure it and start polling
                print(gp.device_info_str())
                connected = True
                while connected:
                    (connected, changed, buttons) = gp.poll()
                    if connected and changed:
                        update_GUI(buttons)
                    sleep(0.001)
                # If loop stopped, gamepad connection was lost
                print("Gamepad disconnected")
                print("Looking for USB gamepad...")
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.1)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(e)
            print("Gamepad connection error")
            print("Looking for USB gamepad...")


main()
