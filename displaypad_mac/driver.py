"""Mountain DisplayPad driver for macOS.

Protocol constants and the upload sequence come from the MIT-licensed
oss-mountain-displaypad project (github.com/AnnikenYT/oss-mountain-displaypad).
The macOS-specific part, verified on hardware, is how each interface is reached:

  IF0  HID keyboard, owned by macOS  -> IOKit, shared open, one SET_REPORT [03 01]
  IF1  pixel data, no macOS driver   -> libusb claims it, interrupt OUT 0x02
  IF3  vendor HID 0xFF00, 64-byte    -> hidapi: commands, ACKs and key events

Without the IF0 report the firmware NAKs every write on IF3 forever, which is
why the Linux driver hangs on a Mac.
"""

import logging
import os
import threading
import time
from typing import Optional, Set

import hid
import usb.core
import usb.util
import usb.backend.libusb1

from .macos import KeyboardInterface

log = logging.getLogger(__name__)

VID, PID = 0x3282, 0x0009
NUM_KEYS = 12
KEYS_PER_ROW = 6
ICON_SIZE = 102
HEADER_SIZE = 306
PACKET_SIZE = 31438
EP_DISPLAY = 0x02

INIT_MSG = bytes([0x00, 0x11, 0x80, 0x00, 0x00, 0x01]) + bytes(59)  # report id 0 + 64 bytes
IMG_MSG = bytearray([0x00, 0x21, 0x00, 0x00, 0x00, 0xFF, 0x3D, 0x00, 0x00, 0x65, 0x65]) + bytearray(54)

# Key bitmap in the 64-byte 0x01 input report: keys 1-7 in byte 42, 8-12 in byte 47.
KEY_MAP = ([(42, m) for m in (0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80)] +
           [(47, m) for m in (0x01, 0x02, 0x04, 0x08, 0x10)])

_LIBUSB_PATHS = ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib")


class DisplayPadError(Exception):
    pass


class PadNotAnswering(DisplayPadError):
    """The pad is on USB but its firmware doesn't answer. Only cutting its power
    (unplugging it) brings it back: a USB port reset keeps it powered, and the
    frozen firmware then can't even send its descriptors, which leaves it worse."""


def device_present() -> bool:
    return any(d.get("interface_number") == 3 for d in hid.enumerate(VID, PID))


def on_usb() -> bool:
    """The pad is plugged in, even if macOS couldn't set it up.

    When the firmware doesn't answer macOS while it is being set up (seen at
    startup, behind a hub), macOS gives up on the command interface (IF3): the
    pad is on USB but device_present() stays False until it is unplugged.
    """
    if hid.enumerate(VID, PID):  # the keyboard interface (IF0) made it
        return True
    try:
        return usb.core.find(idVendor=VID, idProduct=PID, backend=_libusb_backend()) is not None
    except Exception:
        return False


def _libusb_backend():
    for p in _LIBUSB_PATHS:
        if os.path.exists(p):
            return usb.backend.libusb1.get_backend(find_library=lambda _n, p=p: p)
    return usb.backend.libusb1.get_backend()


def decode_keys(report: bytes) -> Optional[Set[int]]:
    """Pressed key indices (0-11) from a raw report, or None if not a key report."""
    if not report or len(report) < 48 or report[0] != 0x01:
        return None
    return {i for i, (b, m) in enumerate(KEY_MAP) if report[b] & m}


class DisplayPad:
    def __init__(self):
        self.kbd: Optional[KeyboardInterface] = None
        self.hid_dev = None
        self.usb_dev = None
        self.connected = False
        self.lock = threading.RLock()
        self._pending: list = []  # key reports that arrived while waiting for ACKs
        self.busy_since: Optional[float] = None  # watchdog: set while blocking I/O runs
        self.last_report: bytes = b""  # the key report read_keys() decoded last (diagnostics)

    # ------------------------------------------------------------ lifecycle
    def open(self):
        with self.lock:
            self.close()
            try:
                self._open()
            except Exception:
                self.close()
                raise
            self.connected = True

    def _open(self):
        path = next((d["path"] for d in hid.enumerate(VID, PID) if d.get("interface_number") == 3), None)
        if path is None:
            raise DisplayPadError("DisplayPad not connected (interface 3 not found)")

        self.kbd = KeyboardInterface(VID, PID)
        self.kbd.open()
        try:
            self.kbd.enable_event_mode()
        except OSError as e:
            if "kIOReturnTimeout" in str(e):  # not a permission problem: the firmware is stuck
                raise PadNotAnswering(str(e)) from e
            raise

        self.hid_dev = hid.device()
        self.hid_dev.open_path(path)
        self.hid_dev.set_nonblocking(False)

        self.usb_dev = usb.core.find(idVendor=VID, idProduct=PID, backend=_libusb_backend())
        if self.usb_dev is None:
            raise DisplayPadError("DisplayPad not visible to libusb")
        usb.util.claim_interface(self.usb_dev, 1)
        try:  # SET_IDLE on the pixel interface; harmless if refused
            self.usb_dev.ctrl_transfer(0x21, 0x0A, 0, 1, None, timeout=500)
        except usb.core.USBError:
            pass

        for _ in range(20):
            self._write(INIT_MSG)
            resp = self._read(500)
            if resp and bytes(resp[:5]) == INIT_MSG[1:6]:
                time.sleep(0.25)  # display engine settles after INIT
                log.info("DisplayPad initialised")
                return
            if resp and decode_keys(bytes(resp)) is not None:
                continue
        raise PadNotAnswering("DisplayPad did not answer the INIT handshake")

    def close(self):
        with self.lock:
            self.connected = False
            if self.usb_dev is not None:
                for fn in (lambda: usb.util.release_interface(self.usb_dev, 1),
                           lambda: usb.util.dispose_resources(self.usb_dev)):
                    try:
                        fn()
                    except Exception:
                        pass
                self.usb_dev = None
            if self.hid_dev is not None:
                try:
                    self.hid_dev.close()
                except Exception:
                    pass
                self.hid_dev = None
            if self.kbd is not None:
                try:
                    self.kbd.close()
                except Exception:
                    pass
                self.kbd = None

    # ------------------------------------------------------------ raw I/O
    def _write(self, data: bytes):
        self.busy_since = time.monotonic()
        try:
            n = self.hid_dev.write(data)
        finally:
            self.busy_since = None
        if n < 0:
            raise DisplayPadError("HID write failed")

    def _read(self, timeout_ms: int):
        data = self.hid_dev.read(64, timeout_ms)
        return data or None

    def _wait_ack(self, b2: int, tries: int = 200) -> bool:
        for _ in range(tries):
            r = self._read(5)
            if not r:
                continue
            if r[0] == 0x21 and r[1] == 0x00 and r[2] == b2:
                return True
            if decode_keys(bytes(r)) is not None:
                self._pending.append(bytes(r))
        return False

    # ------------------------------------------------------------ commands
    def set_brightness(self, percent: int):
        percent = max(0, min(100, int(percent)))
        buf = bytearray(65)
        buf[1], buf[2], buf[5] = 0x12, 0x03, percent
        with self.lock:
            self._require()
            self._write(bytes(buf))

    def upload(self, key: int, bgr: bytes):
        """Send a 102x102 BGR image (31,212 bytes) to key 0-11."""
        if not 0 <= key < NUM_KEYS:
            raise ValueError("key must be 0-11")
        with self.lock:
            self._require()
            msg = bytearray(IMG_MSG)
            msg[5] = key
            self._write(bytes(msg))
            if not self._wait_ack(0x00):
                raise DisplayPadError(f"no ready ACK for key {key}")
            payload = bytearray(HEADER_SIZE + PACKET_SIZE)
            payload[HEADER_SIZE:HEADER_SIZE + len(bgr)] = bgr
            # one transfer: libusb sends the 512-byte packets back to back (one per 125 us
            # microframe) instead of waiting for the host round trip after every 1 KB
            self.usb_dev.write(EP_DISPLAY, bytes(payload), timeout=2000)
            if not self._wait_ack(0xFF):
                raise DisplayPadError(f"no transfer ACK for key {key}")

    def read_keys(self, timeout_ms: int = 50) -> Optional[Set[int]]:
        """Next key-state report as a set of pressed keys, or None if nothing arrived."""
        with self.lock:
            self._require()
            if self._pending:
                r = self._pending.pop(0)
            else:
                r = self._read(timeout_ms)
                if not r:
                    return None
                r = bytes(r)
        keys = decode_keys(r)
        if keys is not None:
            self.last_report = r
        return keys

    def _require(self):
        if not self.connected:
            raise DisplayPadError("DisplayPad not connected")
