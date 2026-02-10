"""Simulated UPS for development and testing without hardware.

Provides a mock serial port that responds to UPS-Link protocol commands.
"""

import threading
import time
import io


class MockUPSPort:
    """Simulates an APC Smart-UPS serial port for testing.

    Implements the same interface as serial.Serial so it can be used
    as a drop-in replacement via monkey-patching.
    """

    # Default simulated UPS state
    DEFAULT_RESPONSES = {
        "Y": "SM",
        "A": "OK",
        "W": "OK",
        "U": "OK",
        "D": "OK",
        "S": "OK",
        "R": "BYE",
        "\x01": "Smart-UPS 2200 XL",    # Ctrl+A — model
        "V": "MWI",                       # Firmware: M=2200, W=revision, I=220V
        "b": "165.12.I",                  # Version in decimal
        "n": "AS1139244203",              # Serial number
        "m": "09/25/11",                  # Manufacture date
        "g": "048",                       # Nominal battery voltage
        "y": "(C) APCC",                  # Copyright
        "f": "100.0",                     # Battery capacity 100%
        "B": "055.35",                    # Battery voltage
        "P": "024.0",                     # Load power %
        "L": "222.4",                     # Line voltage
        "O": "222.4",                     # Output voltage
        "C": "023.8",                     # Temperature
        "F": "50.00",                     # Frequency
        "j": "0120:",                     # Runtime remaining (120 min)
        "M": "225.0",                     # Max line voltage
        "N": "218.0",                     # Min line voltage
        "Q": "08",                        # Status: on-line (bit 3)
        "~": "00",                        # State register
        "'": "00",                        # Trip1 register
        "8": "00",                        # Trip register
        "7": "00",                        # DIP switches
        "G": "O",                         # Transfer cause: none
        "X": "OK",                        # Last test result
        ">": "000",                       # Battery packs
        "<": "000",                       # Bad battery packs
        "9": "FF",                        # Line quality OK
        "E": "336",                       # Self-test every 336h
        "c": "UPS_IDEN",                  # UPS ID
        "x": "09/25/11",                  # Battery replace date
        "u": "253",                       # Upper transfer voltage
        "l": "196",                       # Lower transfer voltage
        "e": "15",                        # Min battery to restart
        "o": "230",                       # Output voltage setting
        "s": "H",                         # Sensitivity: High
        "q": "02",                        # Low battery warning: 2 min
        "k": "0",                         # Alarm: immediate
        "p": "180",                       # Shutdown delay: 180s
        "r": "000",                       # Turn on delay: 0s
        "z": "CLEAR",                     # Reset EEPROM
        # Smart constants (undocumented battery discharge parameters)
        "0": "100",                       # Battery constant (runtime)
        "4": "025",                       # Discharge curve (low)
        "5": "050",                       # Discharge curve (mid)
        "6": "075",                       # Discharge curve (high)
    }

    # EEPROM edit cycle values for each editable command
    EDIT_CYCLES = {
        "E": ["336", "168", "ON ", "OFF"],
        "u": ["253", "264", "271", "280"],
        "l": ["196", "188", "208", "204"],
        "e": ["00", "15", "50", "90"],
        "o": ["225", "230", "240", "220"],
        "s": ["H", "M", "L", "L"],
        "q": ["02", "05", "07", "10"],
        "k": ["0", "T", "L", "N"],
        "p": ["020", "180", "300", "600"],
        "r": ["000", "060", "180", "300"],
        # Battery packs uses direct edit, not cycle — removed from EDIT_CYCLES
    }

    # Commands that use direct character input instead of edit cycling
    DIRECT_EDIT_CMDS = {"c", "x"}
    DIRECT_EDIT_LENGTHS = {"c": 8, "x": 8}

    def __init__(self):
        self.is_open = False
        self._responses = dict(self.DEFAULT_RESPONSES)
        self._edit_state: dict[str, int] = {}  # cmd -> current index in cycle
        self._last_cmd: str | None = None
        self._input_buf = io.BytesIO()
        self._output_buf = io.BytesIO()
        self._lock = threading.Lock()
        self.timeout = 3.0
        self.write_timeout = 3.0
        self.in_waiting = 0
        self._smart_mode = False
        self._prog_mode = False
        self._prog_pending = False  # Waiting for second '1'
        self._prog_value = 222.4  # Simulated calibration value
        self._direct_edit_mode = False  # In direct character input mode
        self._direct_edit_cmd: str | None = None
        self._direct_edit_buf = ""
        self._direct_edit_expected = 0

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._output_buf = io.BytesIO()
            self.in_waiting = 0

    def write(self, data: bytes) -> int:
        with self._lock:
            cmd = data.decode("ascii", errors="replace")
            self._process_command(cmd)
            return len(data)

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            data = self._output_buf.read(size)
            if data:
                self.in_waiting = max(0, self.in_waiting - len(data))
            return data if data else b""

    def read_until(self, terminator: bytes = b"\r\n") -> bytes:
        result = bytearray()
        while True:
            byte = self.read(1)
            if not byte:
                break
            result.extend(byte)
            if result.endswith(terminator):
                break
        return bytes(result)

    def _process_command(self, cmd: str) -> None:
        """Generate a response for the given command."""
        # Direct edit mode: accumulate characters
        if self._direct_edit_mode:
            self._direct_edit_buf += cmd
            if len(self._direct_edit_buf) >= self._direct_edit_expected:
                # All chars received — store new value and respond OK
                self._responses[self._direct_edit_cmd] = self._direct_edit_buf
                self._direct_edit_mode = False
                self._enqueue_response("OK")
            return

        # PROG mode handling
        if self._prog_mode:
            self._handle_prog_command(cmd)
            return

        if cmd == "1":
            if self._prog_pending:
                # Second '1' — enter PROG mode
                self._prog_mode = True
                self._prog_pending = False
                self._enqueue_response("PROG")
            else:
                # First '1' — start waiting
                self._prog_pending = True
            return

        self._prog_pending = False  # Reset if any other command arrives

        if cmd in ("-", "+"):
            # Edit command — cycle the last customizing command
            self._handle_edit(cmd)
            return

        self._last_cmd = cmd

        if cmd in self._responses:
            response = self._responses[cmd]
            self._enqueue_response(response)
        # For unknown commands, no response (matches real UPS behavior)

    def _handle_prog_command(self, cmd: str) -> None:
        """Handle commands while in PROG mode."""
        if cmd == "+":
            self._prog_value += 0.1
            self._enqueue_response(f"{self._prog_value:.1f}")
        elif cmd == "-":
            self._prog_value -= 0.1
            self._enqueue_response(f"{self._prog_value:.1f}")
        elif cmd == "R":
            # Save to EEPROM
            self._enqueue_response("OK")
        elif cmd == "\x1b":
            # ESC — exit PROG mode
            self._prog_mode = False
            self._enqueue_response("BYE")
        elif cmd in self._responses:
            # Read commands still work in PROG mode
            self._enqueue_response(self._responses[cmd])
        else:
            self._enqueue_response("NA")

    def _handle_edit(self, edit_char: str = "-") -> None:
        """Handle the '-' or '+' Edit command by cycling the EEPROM value."""
        cmd = self._last_cmd
        if cmd and cmd in self.EDIT_CYCLES:
            cycle = self.EDIT_CYCLES[cmd]
            if cmd not in self._edit_state:
                # Find current value's index
                current = self._responses.get(cmd, "")
                try:
                    self._edit_state[cmd] = cycle.index(current)
                except ValueError:
                    self._edit_state[cmd] = 0

            # Advance to next value
            self._edit_state[cmd] = (self._edit_state[cmd] + 1) % len(cycle)
            new_value = cycle[self._edit_state[cmd]]
            self._responses[cmd] = new_value
            self._enqueue_response(new_value)
        elif cmd == ">":
            # Battery packs: '+' increments, '-' decrements the raw byte value
            current = int(self._responses.get(">", "000"))
            if edit_char == "+":
                new_val = (current + 1) % 256
            else:
                new_val = (current - 1) % 256
            new_str = f"{new_val:03d}"
            self._responses[">"] = new_str
            self._enqueue_response(new_str)
        elif cmd in self.DIRECT_EDIT_CMDS:
            # Enter direct edit mode — echo current value, then wait for chars
            current = self._responses.get(cmd, "")
            self._enqueue_response(current)
            self._direct_edit_mode = True
            self._direct_edit_cmd = cmd
            self._direct_edit_buf = ""
            self._direct_edit_expected = self.DIRECT_EDIT_LENGTHS.get(cmd, 8)
        else:
            self._enqueue_response("NA")

    def _enqueue_response(self, text: str) -> None:
        """Put a response into the output buffer with CR/LF terminator."""
        response_bytes = (text + "\r\n").encode("ascii")
        # Append to current buffer position
        pos = self._output_buf.tell()
        self._output_buf.seek(0, 2)  # seek to end
        self._output_buf.write(response_bytes)
        self._output_buf.seek(pos)
        self.in_waiting += len(response_bytes)


def create_mock_serial(port: str = "MOCK", **kwargs) -> MockUPSPort:
    """Factory function that creates a MockUPSPort, matching serial.Serial interface."""
    mock = MockUPSPort()
    mock.open()
    return mock
