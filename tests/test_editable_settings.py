"""Tests for editable settings — value cycling logic."""

import unittest

from apc_ups.core.editable_settings import (
    SETTINGS, count_edits_needed, DangerLevel,
)


class TestEditableSettings(unittest.TestCase):

    def test_all_settings_have_required_fields(self):
        for key, setting in SETTINGS.items():
            self.assertTrue(setting.name, f"{key} missing name")
            self.assertTrue(setting.cmd_char, f"{key} missing cmd_char")
            self.assertTrue(setting.state_key, f"{key} missing state_key")

    def test_count_edits_alarm_cycle(self):
        """Alarm control: 0 -> T -> L -> N -> 0 (wraps)."""
        setting = SETTINGS["alarm_control"]
        self.assertEqual(count_edits_needed(setting, "0", "T"), 1)
        self.assertEqual(count_edits_needed(setting, "0", "L"), 2)
        self.assertEqual(count_edits_needed(setting, "0", "N"), 3)
        self.assertEqual(count_edits_needed(setting, "N", "0"), 1)
        self.assertEqual(count_edits_needed(setting, "T", "0"), 3)

    def test_count_edits_self_test(self):
        """Self test: 336 -> 168 -> ON  -> OFF -> 336."""
        setting = SETTINGS["self_test_interval"]
        self.assertEqual(count_edits_needed(setting, "336", "168"), 1)
        self.assertEqual(count_edits_needed(setting, "336", "ON "), 2)
        self.assertEqual(count_edits_needed(setting, "OFF", "336"), 1)

    def test_count_edits_sensitivity_with_duplicate(self):
        """Sensitivity: H -> M -> L -> L. Going from H to L should take 2 steps."""
        setting = SETTINGS["sensitivity"]
        self.assertEqual(count_edits_needed(setting, "H", "M"), 1)
        self.assertEqual(count_edits_needed(setting, "H", "L"), 2)
        self.assertEqual(count_edits_needed(setting, "M", "L"), 1)

    def test_count_edits_already_at_target(self):
        """When current == target, we need a full cycle (wraps around)."""
        setting = SETTINGS["alarm_control"]
        # Must cycle through all 4 to get back to "0"
        self.assertEqual(count_edits_needed(setting, "0", "0"), 4)

    def test_count_edits_invalid_target(self):
        setting = SETTINGS["alarm_control"]
        self.assertIsNone(count_edits_needed(setting, "0", "INVALID"))

    def test_direct_edit_settings(self):
        """UPS ID and battery date are direct edit."""
        self.assertTrue(SETTINGS["ups_id"].direct_edit)
        self.assertTrue(SETTINGS["battery_replace_date"].direct_edit)
        self.assertFalse(SETTINGS["alarm_control"].direct_edit)

    def test_danger_levels(self):
        """Verify danger levels are correctly assigned."""
        self.assertEqual(SETTINGS["self_test_interval"].danger, DangerLevel.NORMAL)
        self.assertEqual(SETTINGS["alarm_control"].danger, DangerLevel.NORMAL)
        self.assertEqual(SETTINGS["ups_id"].danger, DangerLevel.NORMAL)
        self.assertEqual(SETTINGS["sensitivity"].danger, DangerLevel.CAUTION)
        self.assertEqual(SETTINGS["shutdown_delay"].danger, DangerLevel.CAUTION)
        self.assertEqual(SETTINGS["upper_transfer_voltage"].danger, DangerLevel.CAUTION)

    def test_low_battery_warning_values(self):
        setting = SETTINGS["low_battery_warning"]
        self.assertEqual(setting.allowed_values, ["02", "05", "07", "10"])
        self.assertEqual(count_edits_needed(setting, "02", "10"), 3)
        self.assertEqual(count_edits_needed(setting, "10", "02"), 1)

    def test_shutdown_delay_values(self):
        setting = SETTINGS["shutdown_delay"]
        self.assertEqual(setting.allowed_values, ["020", "180", "300", "600"])

    def test_battery_packs_setting(self):
        """Battery packs setting exists and has correct properties."""
        setting = SETTINGS["battery_packs"]
        self.assertEqual(setting.cmd_char, ">")
        self.assertEqual(setting.state_key, "battery_packs")
        self.assertEqual(setting.danger, DangerLevel.CAUTION)
        self.assertFalse(setting.direct_edit)
        self.assertEqual(len(setting.allowed_values), 17)
        self.assertEqual(setting.allowed_values[0], "000")
        self.assertEqual(setting.allowed_values[-1], "016")

    def test_battery_packs_edit_cycle(self):
        """Battery packs cycling from 000 to 001."""
        setting = SETTINGS["battery_packs"]
        self.assertEqual(count_edits_needed(setting, "000", "001"), 1)
        self.assertEqual(count_edits_needed(setting, "000", "016"), 16)
        self.assertEqual(count_edits_needed(setting, "016", "000"), 1)  # wraps


class TestCalibrationPreCheck(unittest.TestCase):
    """Test calibration pre-check with smart constant 0."""

    def test_set_pre_cal_constant_default(self):
        from apc_ups.core.calibration import CalibrationManager
        cal = CalibrationManager()
        cal.set_pre_cal_constant("100", default_value="100")
        self.assertEqual(cal.smart_constant_0, "100")
        self.assertEqual(cal.constant_0_warning, "")

    def test_set_pre_cal_constant_non_default(self):
        from apc_ups.core.calibration import CalibrationManager
        cal = CalibrationManager()
        cal.set_pre_cal_constant("085", default_value="100")
        self.assertEqual(cal.smart_constant_0, "085")
        self.assertIn("085", cal.constant_0_warning)
        self.assertIn("default", cal.constant_0_warning)

    def test_calibration_reset_clears_constant(self):
        from apc_ups.core.calibration import CalibrationManager
        cal = CalibrationManager()
        cal.set_pre_cal_constant("085", default_value="100")
        cal.reset()
        self.assertEqual(cal.smart_constant_0, "")
        self.assertEqual(cal.constant_0_warning, "")


class TestBatteryAge(unittest.TestCase):
    """Test battery age computation."""

    def test_compute_battery_age(self):
        from apc_ups.core.ups_state import UPSState
        from apc_ups.core.ups_manager import UPSManager
        manager = UPSManager()
        # Set a date 365 days ago (approximate)
        from datetime import datetime, timedelta
        past = datetime.now() - timedelta(days=365)
        manager.state.update(battery_replace_date=past.strftime("%m/%d/%y"))
        manager._compute_battery_age()
        age = manager.state.battery_age_days
        # Should be approximately 365 days (allow 1 day tolerance)
        self.assertGreaterEqual(age, 364)
        self.assertLessEqual(age, 366)

    def test_compute_battery_age_unknown(self):
        from apc_ups.core.ups_manager import UPSManager
        manager = UPSManager()
        manager.state.update(battery_replace_date="---")
        manager._compute_battery_age()
        self.assertEqual(manager.state.battery_age_days, -1)


if __name__ == "__main__":
    unittest.main()
