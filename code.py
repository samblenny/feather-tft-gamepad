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

import adafruit_imageload
from adafruit_st7789 import ST7789
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, L, R, A, B, X, Y)


def update_GUI(scene, prev, buttons):
    # Update TileGrid sprites to reflect changed state of gamepad buttons
    # Scene is 10 sprites wide by 5 sprites tall:
    #  Y
    #  0 . L . . . . . . R .
    #  1 . . dU. . . . X . .
    #  2 . dL. dR. . Y . A .
    #  3 . . dD. SeSt. B . .
    #  4 . . . . . . . . . .
    #    0 1 2 3 4 5 6 7 8 9 X
    #
    diff = prev ^  buttons
    if diff & A:
        scene[8, 2] = 15 if (buttons & A) else 17
    if diff & B:
        scene[7, 3] = 15 if (buttons & B) else 17
    if diff & X:
        scene[7, 1] = 15 if (buttons & X) else 17
    if diff & Y:
        scene[6, 2] = 15 if (buttons & Y) else 17
    if diff & L:
        scene[1, 0] = 1 if (buttons & L) else 5
    if diff & R:
        scene[8, 0] = 1 if (buttons & R) else 5
    if diff & UP:
        scene[2, 1] = 8 if (buttons & UP) else 12
    if diff & DOWN:
        scene[2, 3] = 22 if (buttons & DOWN) else 26
    if diff & LEFT:
        scene[1, 2] = 14 if (buttons & LEFT) else 18
    if diff & RIGHT:
        scene[3, 2] = 16 if (buttons & RIGHT) else 20
    if diff & SELECT:
        scene[4, 3] = 10 if (buttons & SELECT) else 24
    if diff & START:
        scene[5, 3] = 11 if (buttons & START) else 25
    #print(f"{buttons:016b}")


def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize display
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()
    # load spritesheet and palette
    (bitmap, palette) = adafruit_imageload.load("sprites.bmp", bitmap=Bitmap,
        palette=Palette)
    # assemble TileGrid with gamepad using sprites from the spritesheet
    scene = TileGrid(bitmap, pixel_shader=palette, width=10, height=5,
        tile_width=8, tile_height=8, default_tile=9)
    tilemap = (
        (0, 5, 2, 3, 3, 3, 3, 4, 5, 6),            # . L . . . . . . R .
        (7, 9, 12, 9, 9, 9, 9, 17, 9, 13),         # . . dU. . . . X . .
        (7, 18, 19, 20, 9, 9, 17, 9, 17, 13),      # . dL. dR. . Y . A .
        (7, 9, 26, 9, 24, 25, 9, 17, 9, 13),       # . . dD. SeSt. B . .
        (21, 23, 23, 23, 23, 23, 23, 23, 23, 27),  # . . . . . . . . . .
    )
    for (y, row) in enumerate(tilemap):
        for (x, sprite) in enumerate(row):
            scene[x, y] = sprite
    grp = Group(scale=3)  # 3x zoom
    grp.append(scene)
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
                prev = 0
                while connected:
                    (connected, changed, buttons) = gp.poll()
                    if connected and changed:
                        update_GUI(scene, prev, buttons)
                        display.refresh()
                        prev = buttons
                    sleep(0.002)
                    gc.collect()
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
