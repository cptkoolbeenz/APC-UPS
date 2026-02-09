"""Tests for register decoder utility."""

import unittest

from apc_ups.util.register_decoder import (
    decode_status, decode_state, decode_trip1, decode_trip,
    decode_hex_register,
)
from apc_ups.protocol.constants import STATUS_BITS


class TestRegisterDecoder(unittest.TestCase):

    def test_decode_status_online(self):
        """Status 08 = on-line mode (bit 3)."""
        result = decode_status("08")
        self.assertTrue(result["On Line"])
        self.assertFalse(result["On Battery"])
        self.assertFalse(result["Low Battery"])
        self.assertFalse(result["Replace Battery"])
        self.assertFalse(result["Runtime Calibration"])

    def test_decode_status_on_battery(self):
        """Status 10 = on-battery (bit 4)."""
        result = decode_status("10")
        self.assertTrue(result["On Battery"])
        self.assertFalse(result["On Line"])

    def test_decode_status_multiple_bits(self):
        """Status 18 = on-line + on-battery (bits 3 and 4)."""
        result = decode_status("18")
        self.assertTrue(result["On Line"])
        self.assertTrue(result["On Battery"])

    def test_decode_status_low_replace(self):
        """Status C8 = replace + low battery + on-line."""
        result = decode_status("C8")
        self.assertTrue(result["Replace Battery"])
        self.assertTrue(result["Low Battery"])
        self.assertTrue(result["On Line"])

    def test_decode_status_calibration(self):
        """Status 09 = on-line + calibration running."""
        result = decode_status("09")
        self.assertTrue(result["On Line"])
        self.assertTrue(result["Runtime Calibration"])

    def test_decode_status_smartboost(self):
        """Status 0C = on-line + SmartBoost."""
        result = decode_status("0C")
        self.assertTrue(result["On Line"])
        self.assertTrue(result["SmartBoost"])

    def test_decode_status_invalid_hex(self):
        """Invalid hex string should return all False."""
        result = decode_status("ZZ")
        self.assertFalse(any(result.values()))

    def test_decode_state_all_clear(self):
        result = decode_state("00")
        self.assertFalse(any(result.values()))

    def test_decode_trip1_fan_failure(self):
        """Trip1 01 = Electronics fan failure (bit 0)."""
        result = decode_trip1("01")
        self.assertTrue(result["UPS fault — Electronics Unit fan failure; UPS is in bypass"])

    def test_decode_trip_low_battery_shutdown(self):
        """Trip 01 = low battery shut down (bit 0)."""
        result = decode_trip("01")
        self.assertTrue(result["UPS output unpowered due to low battery shut down"])

    def test_decode_trip_charger_failure(self):
        """Trip 20 = battery charger failure (bit 5)."""
        result = decode_trip("20")
        self.assertTrue(result["UPS fault — battery charger failure"])


if __name__ == "__main__":
    unittest.main()
