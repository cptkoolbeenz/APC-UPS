"""Thin pyserial wrapper with thread-safe locking."""

import time
import threading
import serial

from apc_ups.protocol.constants import (
    BAUD_RATE, BYTE_SIZE, STOP_BITS, PARITY,
    TIMEOUT, WRITE_TIMEOUT, RESPONSE_TERMINATOR,
)


class SerialConnection:
    """Thread-safe serial port wrapper for UPS communication."""

    # Delay after closing before the port can be reopened (seconds).
    # CH340 and similar USB-serial adapters need time to reset.
    POST_CLOSE_DELAY = 1.0

    # Retry parameters for open() — CH340 adapters may need several
    # seconds after close before they accept a new connection.
    OPEN_RETRIES = 4
    OPEN_RETRY_DELAY = 1.0  # seconds between retries

    def __init__(self):
        self._port: serial.Serial | None = None
        self._lock = threading.Lock()

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def is_open(self) -> bool:
        return self._port is not None and self._port.is_open

    def open(self, port: str) -> None:
        """Open the serial port with UPS-Link parameters.

        Retries up to OPEN_RETRIES times if the port is temporarily
        unavailable (PermissionError / SerialException), which is common
        with CH340 USB-serial adapters that need time to reset after close.
        """
        with self._lock:
            if self._port and self._port.is_open:
                self._close_port_locked()
                time.sleep(self.POST_CLOSE_DELAY)

            last_error: Exception | None = None
            for attempt in range(self.OPEN_RETRIES):
                try:
                    self._port = serial.Serial(
                        port=port,
                        baudrate=BAUD_RATE,
                        bytesize=BYTE_SIZE,
                        stopbits=STOP_BITS,
                        parity=PARITY,
                        timeout=TIMEOUT,
                        write_timeout=WRITE_TIMEOUT,
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                    )
                    return  # Success
                except (PermissionError, serial.SerialException) as e:
                    last_error = e
                    if attempt < self.OPEN_RETRIES - 1:
                        time.sleep(self.OPEN_RETRY_DELAY)

            # All retries exhausted — raise the last error
            raise last_error

    def close(self) -> None:
        """Close the serial port gracefully.

        Flushes buffers, drops control lines, closes the port, then waits
        briefly for the USB-serial driver to fully release.
        Does NOT call cancel_read() — that can crash CH340 and similar
        USB-serial adapters on Windows.
        """
        with self._lock:
            self._close_port_locked()

        # Let the USB-serial driver finish releasing the port.
        # Without this pause, CH340 adapters refuse to reopen.
        time.sleep(self.POST_CLOSE_DELAY)

    def _close_port_locked(self) -> None:
        """Internal close — must be called while holding self._lock."""
        if not self._port:
            return
        if self._port.is_open:
            try:
                self._port.reset_input_buffer()
            except (OSError, serial.SerialException):
                pass
            try:
                self._port.flush()
            except (OSError, serial.SerialException):
                pass
            # Drop DTR/RTS before closing — helps CH340 reset cleanly
            try:
                self._port.dtr = False
                self._port.rts = False
            except (OSError, serial.SerialException, AttributeError):
                pass
            try:
                self._port.close()
            except (OSError, serial.SerialException):
                pass
        self._port = None

    def write(self, data: bytes) -> None:
        """Write bytes to the serial port. Caller must hold the lock."""
        if not self._port or not self._port.is_open:
            raise ConnectionError("Serial port is not open")
        self._port.write(data)

    def read(self, size: int = 1) -> bytes:
        """Read up to `size` bytes. Caller must hold the lock."""
        if not self._port or not self._port.is_open:
            raise ConnectionError("Serial port is not open")
        return self._port.read(size)

    def read_until(self, terminator: bytes = RESPONSE_TERMINATOR,
                   timeout: float | None = None) -> bytes:
        """Read until terminator is found or timeout expires.

        Caller must hold the lock.
        """
        if not self._port or not self._port.is_open:
            raise ConnectionError("Serial port is not open")
        old_timeout = self._port.timeout
        if timeout is not None:
            self._port.timeout = timeout
        try:
            data = self._port.read_until(terminator)
            return data
        finally:
            if timeout is not None:
                self._port.timeout = old_timeout

    def flush_input(self) -> None:
        """Discard all data in the input buffer. Caller must hold the lock."""
        if self._port and self._port.is_open:
            self._port.reset_input_buffer()

    def in_waiting(self) -> int:
        """Return number of bytes waiting in the input buffer. Caller must hold the lock."""
        if not self._port or not self._port.is_open:
            return 0
        return self._port.in_waiting
