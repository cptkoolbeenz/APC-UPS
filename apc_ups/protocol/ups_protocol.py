"""UPS-Link protocol handler — command send/receive with async alert filtering."""

import time
import logging
from typing import Callable

from apc_ups.protocol.serial_conn import SerialConnection
from apc_ups.protocol.constants import (
    ALERT_CHARS, RESPONSE_TERMINATOR, TIMED_CMD_DELAY, EEPROM_WRITE_DELAY,
    SMART_MODE_CMD, SMART_MODE_RESPONSE,
    PROG_MODE_CMD, PROG_MODE_DELAY, PROG_MODE_RESPONSE,
)

logger = logging.getLogger(__name__)

# Control character display names for protocol logging
_CTRL_NAMES = {
    "\x01": "<Ctrl+A>", "\x0e": "<Ctrl+N>", "\x1b": "<ESC>",
    "\x7f": "<DEL>", "\x16": "<Ctrl+V>", "\x0c": "<Ctrl+L>",
    "\x1a": "<Ctrl+Z>",
}


def _format_control(data: str) -> str:
    """Replace control characters with readable names for display."""
    out = []
    for ch in data:
        if ch in _CTRL_NAMES:
            out.append(_CTRL_NAMES[ch])
        elif ord(ch) < 0x20:
            out.append(f"<0x{ord(ch):02X}>")
        else:
            out.append(ch)
    return "".join(out)


AlertCallback = Callable[[str], None]
IOCallback = Callable[[str, str], None]  # (direction "TX"/"RX", data)


class UPSProtocol:
    """Handles sending commands and parsing responses over the serial link."""

    def __init__(self, conn: SerialConnection,
                 alert_callback: AlertCallback | None = None,
                 io_callback: IOCallback | None = None):
        self._conn = conn
        self._alert_callback = alert_callback
        self._io_callback = io_callback

    def _log_tx(self, data: str) -> None:
        """Log transmitted data."""
        if self._io_callback:
            # Show control chars as readable names
            display = _format_control(data)
            self._io_callback("TX", display)

    def _log_rx(self, data: str | None) -> None:
        """Log received data."""
        if self._io_callback:
            self._io_callback("RX", data if data is not None else "(timeout)")

    @property
    def connection(self) -> SerialConnection:
        return self._conn

    def _dispatch_alert(self, char: str) -> None:
        """Forward an async alert character to the callback."""
        logger.info("Async alert received: %r", char)
        if self._alert_callback:
            self._alert_callback(char)

    def enter_smart_mode(self) -> bool:
        """Send 'Y' and verify 'SM' response to enter smart signaling mode.

        Returns True on success.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(SMART_MODE_CMD)
            self._conn.write(SMART_MODE_CMD.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)
        return response == SMART_MODE_RESPONSE

    def send_command(self, cmd_char: str) -> str | None:
        """Send a single-character command and return the response string.

        Filters out any async alert characters received mid-response.
        Returns None if no valid response was received.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(cmd_char)
            self._conn.write(cmd_char.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_timed_command(self, cmd_char: str) -> str | None:
        """Send a timed command sequence (e.g. K...K or Z...Z).

        Sends cmd_char, waits >1.5s, sends cmd_char again.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(f"{cmd_char} (timed 1/2)")
            self._conn.write(cmd_char.encode("ascii"))
        time.sleep(TIMED_CMD_DELAY)
        with self._conn.lock:
            self._log_tx(f"{cmd_char} (timed 2/2)")
            self._conn.write(cmd_char.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_timed_ctrl_n(self) -> str | None:
        """Send Ctrl+N(>1.5s)Ctrl+N to turn UPS on."""
        return self.send_timed_command("\x0e")

    def send_edit(self) -> str | None:
        """Send the Edit command '-' and return the response.

        Must be sent directly after a customizing command.
        For multi-step edits, use send_setting_edit() which re-sends
        the command before each '-' per the UPS-Link spec.
        """
        with self._conn.lock:
            self._log_tx("-")
            self._conn.write(b"-")
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_setting_edit(self, cmd_char: str) -> tuple[str | None, str | None]:
        """Send a customizing command then '-' to advance to the next EEPROM value.

        Per the UPS-Link spec, the '-' Edit command must come "directly
        following" the customizing command. This method sends cmd_char,
        reads the current value, sends '-', reads the edit response,
        and waits for the EEPROM write to complete.

        Returns (current_value, edit_response).
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(cmd_char)
            self._conn.write(cmd_char.encode("ascii"))
            current = self._read_response_locked()
            self._log_rx(current)

            self._log_tx("-")
            self._conn.write(b"-")
            edit_resp = self._read_response_locked()
            self._log_rx(edit_resp)

        # Allow EEPROM write to complete before next command
        time.sleep(EEPROM_WRITE_DELAY)
        return current, edit_resp

    def send_battery_packs_adjust(self, direction: str) -> str | None:
        """Adjust battery packs count by sending '>' then '+' or '-'.

        Per UPS-Link spec, the '>' command must be re-sent before each
        '+' or '-' adjustment. Returns the new value string.
        """
        if direction not in ("+", "-"):
            raise ValueError("direction must be '+' or '-'")
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(">")
            self._conn.write(b">")
            # Read current value (we discard it, just need UPS in '>' context)
            current = self._read_response_locked()
            self._log_rx(current)

            self._log_tx(direction)
            self._conn.write(direction.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)

        # Allow EEPROM write to complete before next command
        time.sleep(EEPROM_WRITE_DELAY)
        return response

    def send_direct_edit(self, cmd_char: str, text: str) -> str | None:
        """Send a direct-edit command (c for UPS ID, x for battery date, > for packs).

        Sequence: send cmd_char (reads current value), send '-' to enter edit,
        read the edit-mode response, then send each character of `text`,
        then read OK response.
        """
        with self._conn.lock:
            # Read current value
            self._conn.flush_input()
            self._log_tx(cmd_char)
            self._conn.write(cmd_char.encode("ascii"))
            current = self._read_response_locked()
            self._log_rx(current)
            logger.debug("Direct edit %r current value: %r", cmd_char, current)

            # Enter edit mode — UPS responds (may echo value or send NO)
            self._log_tx("- (enter edit)")
            self._conn.write(b"-")
            edit_response = self._read_response_locked()
            self._log_rx(edit_response)
            logger.debug("Direct edit %r after '-': %r", cmd_char, edit_response)

            # If UPS rejected the edit, abort
            if edit_response and edit_response.strip() in ("NO", "NA"):
                return edit_response.strip()

            # Type each character of the new value
            self._log_tx(f"'{text}' (direct input)")
            for ch in text:
                self._conn.write(ch.encode("ascii"))
                time.sleep(0.05)  # Small delay between chars for UPS to process

            # Read OK response
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_shutdown_with_wake(self, tenths_of_hour: int) -> str | None:
        """Send @ddd command for shutdown with delayed wake up."""
        cmd = f"@{tenths_of_hour:03d}"
        with self._conn.lock:
            self._conn.flush_input()
            self._conn.write(cmd.encode("ascii"))
            return self._read_response_locked()

    def send_abort_shutdown(self) -> str | None:
        """Send DEL character to abort a pending shutdown."""
        return self.send_command("\x7f")

    # --- PROG Mode (undocumented service/calibration mode) ---

    def enter_prog_mode(self) -> bool:
        """Enter PROG mode: send '1', wait 4 seconds, send '1' again.

        UPS responds with 'PROG' on success.
        Returns True if PROG mode was entered successfully.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx("1 (PROG 1/2)")
            self._conn.write(PROG_MODE_CMD.encode("ascii"))
        time.sleep(PROG_MODE_DELAY)
        with self._conn.lock:
            self._log_tx("1 (PROG 2/2)")
            self._conn.write(PROG_MODE_CMD.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)
        return response == PROG_MODE_RESPONSE

    def send_prog_adjust(self, direction: str) -> str | None:
        """Adjust a value in PROG mode using '+' or '-'.

        Args:
            direction: '+' to increase, '-' to decrease
        Returns the new value string, or None on timeout.
        """
        if direction not in ("+", "-"):
            raise ValueError("direction must be '+' or '-'")
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx(f"{direction} (PROG adjust)")
            self._conn.write(direction.encode("ascii"))
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_prog_save(self) -> str | None:
        """Save the adjusted value in PROG mode (sends 'R').

        Note: 'R' in PROG mode means 'save to EEPROM', NOT 'return to simple mode'.
        Returns the UPS response.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx("R (PROG save)")
            self._conn.write(b"R")
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def exit_prog_mode(self) -> str | None:
        """Exit PROG mode by sending ESC (0x1B).

        Returns the UPS response, if any.
        """
        with self._conn.lock:
            self._conn.flush_input()
            self._log_tx("<ESC> (exit PROG)")
            self._conn.write(b"\x1b")
            response = self._read_response_locked()
            self._log_rx(response)
            return response

    def send_prog_read_command(self, cmd_char: str) -> str | None:
        """Read a value while in PROG mode.

        Args:
            cmd_char: The command character (e.g. 'L' for line voltage)
        Returns the current value.
        """
        return self.send_command(cmd_char)

    def _read_response_locked(self) -> str | None:
        """Read a response, filtering out async alert characters.

        Must be called while holding self._conn.lock.
        Returns the response string stripped of the CR/LF terminator, or None on timeout.
        """
        buf = bytearray()
        terminator = RESPONSE_TERMINATOR

        while True:
            byte = self._conn.read(1)
            if not byte:
                # Timeout
                if buf:
                    result = buf.decode("ascii", errors="replace").strip()
                    return result if result else None
                return None

            char = byte.decode("ascii", errors="replace")

            # Check if this is an async alert character
            if char in ALERT_CHARS and len(buf) == 0:
                # Alert at start of read — dispatch and continue reading
                self._dispatch_alert(char)
                continue
            elif char in ALERT_CHARS:
                # Alert in the middle of a response — dispatch but don't add to buffer
                self._dispatch_alert(char)
                continue

            buf.extend(byte)

            # Check for terminator
            if buf.endswith(terminator):
                result = buf[:-len(terminator)].decode("ascii", errors="replace")
                return result.strip() if result else None
