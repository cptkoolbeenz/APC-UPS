"""Tests for protocol layer — command/response parsing, async alert filtering."""

import unittest
from unittest.mock import MagicMock

from tests.mock_ups import MockUPSPort
from apc_ups.protocol.serial_conn import SerialConnection
from apc_ups.protocol.ups_protocol import UPSProtocol


class TestMockUPS(unittest.TestCase):
    """Test the mock UPS port directly."""

    def setUp(self):
        self.mock = MockUPSPort()
        self.mock.open()

    def test_smart_mode(self):
        self.mock.write(b"Y")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"SM\r\n")

    def test_battery_capacity(self):
        self.mock.write(b"f")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"100.0\r\n")

    def test_status_register(self):
        self.mock.write(b"Q")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"08\r\n")

    def test_model_name(self):
        self.mock.write(b"\x01")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"Smart-UPS 2200 XL\r\n")

    def test_edit_cycle(self):
        # Read current self-test value
        self.mock.write(b"E")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"336\r\n")

        # Edit to next value
        self.mock.write(b"-")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"168\r\n")

        # Edit again
        self.mock.write(b"-")
        response = self.mock.read_until(b"\r\n")
        self.assertEqual(response, b"ON \r\n")

    def test_edit_cycle_wraps(self):
        """Edit cycling wraps around to the first value."""
        self.mock.write(b"k")
        self.mock.read_until(b"\r\n")  # 0

        values = []
        for _ in range(5):
            self.mock.write(b"-")
            resp = self.mock.read_until(b"\r\n").decode().strip()
            values.append(resp)

        # Should wrap: T, L, N, 0, T
        self.assertEqual(values, ["T", "L", "N", "0", "T"])


class TestProtocolWithMock(unittest.TestCase):
    """Test UPSProtocol using a mock serial connection."""

    def setUp(self):
        self.mock_port = MockUPSPort()
        self.mock_port.open()
        self.conn = SerialConnection()
        # Monkey-patch the serial port
        self.conn._port = self.mock_port
        self.alerts = []
        self.protocol = UPSProtocol(self.conn, alert_callback=self.alerts.append)

    def test_enter_smart_mode(self):
        result = self.protocol.enter_smart_mode()
        self.assertTrue(result)

    def test_send_command_battery(self):
        result = self.protocol.send_command("f")
        self.assertEqual(result, "100.0")

    def test_send_command_status(self):
        result = self.protocol.send_command("Q")
        self.assertEqual(result, "08")

    def test_send_command_model(self):
        result = self.protocol.send_command("\x01")
        self.assertEqual(result, "Smart-UPS 2200 XL")

    def test_send_edit(self):
        # First read current value
        self.protocol.send_command("E")
        # Then edit
        result = self.protocol.send_edit()
        self.assertEqual(result, "168")

    def test_send_setting_edit(self):
        """send_setting_edit sends cmd then '-' as a single operation."""
        # Self test: 336 → 168
        current, edit_resp = self.protocol.send_setting_edit("E")
        self.assertEqual(current, "336")
        self.assertEqual(edit_resp, "168")

    def test_send_setting_edit_multi_step(self):
        """Multi-step edit re-sends cmd before each '-'."""
        # Sensitivity: H → M → L (2 steps)
        current1, resp1 = self.protocol.send_setting_edit("s")
        self.assertEqual(current1, "H")
        self.assertEqual(resp1, "M")

        current2, resp2 = self.protocol.send_setting_edit("s")
        self.assertEqual(current2, "M")
        self.assertEqual(resp2, "L")

    def test_line_voltage(self):
        result = self.protocol.send_command("L")
        self.assertEqual(result, "222.4")

    def test_serial_number(self):
        result = self.protocol.send_command("n")
        self.assertEqual(result, "AS1139244203")

    def test_smart_constants(self):
        """Read undocumented smart constants 0, 4, 5, 6."""
        self.assertEqual(self.protocol.send_command("0"), "100")
        self.assertEqual(self.protocol.send_command("4"), "025")
        self.assertEqual(self.protocol.send_command("5"), "050")
        self.assertEqual(self.protocol.send_command("6"), "075")

    def test_battery_packs_edit(self):
        """Adjust battery packs via > then +/- per UPS-Link spec."""
        result = self.protocol.send_command(">")
        self.assertEqual(result, "000")
        # > then - : 000 → 255
        result = self.protocol.send_battery_packs_adjust("-")
        self.assertEqual(result, "255")
        # > then - again: 255 → 254
        result = self.protocol.send_battery_packs_adjust("-")
        self.assertEqual(result, "254")
        # > then + : 254 → 255
        result = self.protocol.send_battery_packs_adjust("+")
        self.assertEqual(result, "255")

    def test_prog_mode_enter(self):
        """Test PROG mode entry via mock."""
        # Send first '1' — no response
        self.mock_port.write(b"1")
        # Send second '1' — should get PROG
        self.mock_port.write(b"1")
        response = self.mock_port.read_until(b"\r\n")
        self.assertEqual(response, b"PROG\r\n")

    def test_prog_mode_adjust(self):
        """Test PROG mode +/- adjustment via mock."""
        # Enter PROG mode
        self.mock_port.write(b"1")
        self.mock_port.write(b"1")
        self.mock_port.read_until(b"\r\n")  # consume PROG

        # Adjust +
        self.mock_port.write(b"+")
        response = self.mock_port.read_until(b"\r\n")
        self.assertIn(b"222.5", response)

        # Adjust -
        self.mock_port.write(b"-")
        response = self.mock_port.read_until(b"\r\n")
        self.assertIn(b"222.4", response)

    def test_prog_mode_save_and_exit(self):
        """Test PROG mode save and exit."""
        # Enter PROG mode
        self.mock_port.write(b"1")
        self.mock_port.write(b"1")
        self.mock_port.read_until(b"\r\n")  # consume PROG

        # Save
        self.mock_port.write(b"R")
        response = self.mock_port.read_until(b"\r\n")
        self.assertEqual(response, b"OK\r\n")

        # Exit (ESC)
        self.mock_port.write(b"\x1b")
        response = self.mock_port.read_until(b"\r\n")
        self.assertEqual(response, b"BYE\r\n")


if __name__ == "__main__":
    unittest.main()
