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
# | TFT feather | USB Host |
# | ----------- | -------- |
# |  SCK        |  SCK     |
# |  MOSI       |  MOSI    |
# |  MISO       |  MISO    |
# |  D9         |  IRQ     |
# |  D10        |  CS      |
#
from board import D9, D10, SPI
from digitalio import DigitalInOut, Direction
from displayio import release_displays
import gc
from max3421e import Max3421E
from struct import unpack
from sys import stdout
from time import sleep
from usb import core


# Gamepad button bitmask constants
BTN = {
    'dUp':    0x0001,
    'dDn':    0x0002,
    'dL':     0x0004,
    'dR':     0x0008,
    'Start':  0x0010,
    'Select': 0x0020,
    'LHat':   0x0040,
    'RHat':   0x0080,
    'L':      0x0100,
    'R':      0x0200,
    'Home':   0x0400,
    'B':      0x1000,
    'A':      0x2000,
    'Y':      0x4000,
    'X':      0x8000,
    }

def decode(btn, L2, R2):
    # Decode the button bitfield along with L2 and R2
    names = []
    for k in sorted(BTN):
        v = BTN[k]
        if btn & v:
            names.append(k)
    if L2:
        names.append("L2")
    if R2:
        names.append("R2")
    return " ".join(names)

def start_xpad(device):
    # Initialize gamepad and poll for input changes, print updates
    interface = 0
    timeout_ms = 5
    prev14 = bytearray(14)
    buf64 = bytearray(64)
    # Make sure CircuitPython core is not claiming the device
    if device.is_kernel_driver_active(interface):
        print("detaching kernel driver")
        device.detach_kernel_driver(interface)
        sleep(0.1)
    # Print device details
    (vid, pid) = (device.idVendor, device.idProduct)
    (prod, mfg) = (device.product, device.manufacturer)
    print(" found: %04x:%04x '%s', '%s'" % (vid, pid, prod, mfg))
    if (vid, pid) == (0, 0):
        # I've seen vid:pid = 0000:0000 happen when I tried using a wireless
        # adapter. Might be a bug?
        print("bad connection, (trying again)")
        return
    # Make sure that configuration is set
    try:
        print("setting configuration")
        device.set_configuration()
        sleep(0.1)
    except core.USBError as e:
        print("usberr1:", e.errno, e)
        raise e
    # Initial reads may give old data, so drain gamepad's buffer
    for _ in range(8):
        try:
            _ = device.read(0x81, buf64, timeout=timeout_ms)
        except core.USBError as e:
            print("usberr2:", e.errno, e)
            if e.errno == None:
                # This happened when I tried a wireless adapter
                print("endpoint 0x81 read failed, disconnecting")
                return
    # Start polling for input events
    while True:
        sleep(0.005)  # delay a bit before polling again
        try:
            n = device.read(0x81, buf64, timeout=timeout_ms)
        except core.USBError as e:
            print("usberr3:", e.errno, e)
            if e.errno == None:  # Happens when USB cable unplugged
                return
            else:
                raise e
        if n < 14:
            # skip unexpected responses (looking for a 20 byte report)
            continue
        buf14 = buf64[:14]
        if buf14 != prev14:
            # Unpack normal responses
            prev14[:] = buf14
            (btn, L2, R2, LX, LY, RX, RY) = unpack('<HBBhhhh', buf14[2:14])
            print("(%6d,%6d)  (%6d,%6d) " % (LX, LY, RX, RY),
                decode(btn, L2, R2))

def find_and_connect():
    # Attempt to establish a gamepad connection
    print("Looking for USB gamepads...")
    while True:
        gamepad = core.find(idVendor=0x045e, idProduct=0x028e)
        if gamepad:
            try:
                return start_xpad(gamepad)
            except core.USBError as e:
                print("usberr4:", e.errno, e)
                raise e
        else:
            # If no gamepads are connected, try again
            sleep(0.1)

def main():
    release_displays()  # TFT console slows down gamepad polling
    gc.collect()

    # Initializing MAX3421E USB host chip
    print("Initializing USB host port...")
    spi = SPI()
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    while True:
        find_and_connect()  # returns if connection is lost
        sleep(0.1)
        gc.collect()


main()
