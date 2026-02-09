"""Thin pyserial wrapper with thread-safe locking."""

import threading
import serial

from apc_ups.protocol.constants import (
    BAUD_RATE, BYTE_SIZE, STOP_BITS, PARITY,
    TIMEOUT, WRITE_TIMEOUT, RESPONSE_TERMINATOR,
)


class SerialConnection:
    """Thread-safe serial port wrapper for UPS communication."""

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
        """Open the serial port with UPS-Link parameters."""
        with self._lock:
            if self._port and self._port.is_open:
                self._port.close()
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

    def close(self) -> None:
        """Close the serial port gracefully.

        Flushes the output buffer and cancels pending reads before closing.
        """
        # Cancel any pending read (without lock, to unblock a reader thread)
        port = self._port
        if port is not None:
            try:
                port.cancel_read()
            except (AttributeError, OSError):
                pass  # cancel_read not available on all platforms/versions

        with self._lock:
            if self._port and self._port.is_open:
                try:
                    self._port.reset_input_buffer()
                except (OSError, serial.SerialException):
                    pass
                try:
                    self._port.flush()  # Drain output buffer
                except (OSError, serial.SerialException):
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
