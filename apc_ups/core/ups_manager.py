"""High-level UPS orchestrator — connect, poll, change settings."""

import time
import threading
import logging
from datetime import datetime
from typing import Callable

from apc_ups.protocol.serial_conn import SerialConnection
from apc_ups.protocol.ups_protocol import UPSProtocol
from apc_ups.protocol.commands import COMMANDS, FAST_POLL_CMDS, SLOW_POLL_CMDS, ONCE_CMDS
from apc_ups.protocol.constants import (
    ALERT_DESCRIPTIONS, DEFAULT_TEMP_ALERT_THRESHOLD, BATTERY_AGE_WARNING_DAYS,
)
from apc_ups.core.ups_state import UPSState
from apc_ups.core.editable_settings import SETTINGS, count_edits_needed, EditableSetting
from apc_ups.core.calibration import CalibrationManager, CalibrationState

logger = logging.getLogger(__name__)

# Mapping from command chars to UPSState attribute names for readings
CMD_TO_STATE_KEY = {
    "\x01": "model",
    "V": "firmware",
    "b": "firmware_decimal",
    "n": "serial_number",
    "m": "manufacture_date",
    "y": "copyright_str",
    "g": "nominal_battery_voltage",
    "f": "battery_capacity",
    "B": "battery_voltage",
    "P": "load_power",
    "L": "input_voltage",
    "O": "output_voltage",
    "Q": "status_register",
    "C": "temperature",
    "F": "frequency",
    "j": "runtime_remaining",
    "M": "max_line_voltage",
    "N": "min_line_voltage",
    "~": "state_register",
    "'": "trip1_register",
    "8": "trip_register",
    "7": "dip_switch",
    "G": "transfer_cause",
    "X": "last_test_result",
    ">": "battery_packs",
    "<": "bad_battery_packs",
    "0": "smart_constant_0",
    "4": "smart_constant_4",
    "5": "smart_constant_5",
    "6": "smart_constant_6",
    "E": "self_test_interval",
    "c": "ups_id",
    "x": "battery_replace_date",
    "u": "upper_transfer_voltage",
    "l": "lower_transfer_voltage",
    "e": "min_battery_restart",
    "o": "output_voltage_setting",
    "s": "sensitivity",
    "q": "low_battery_warning",
    "k": "alarm_control",
    "p": "shutdown_delay",
    "r": "turn_on_delay",
}

# Numeric fields that should be parsed as floats
NUMERIC_FIELDS = {
    "battery_capacity", "battery_voltage", "load_power", "input_voltage",
    "output_voltage", "temperature", "frequency", "runtime_remaining",
    "max_line_voltage", "min_line_voltage",
}

# UPS model wattage ratings (approximate, for load W calculation)
MODEL_WATTAGE = {
    "Smart-UPS 450": 280, "Smart-UPS 700": 450, "Smart-UPS 1000": 670,
    "Smart-UPS 1400": 950, "Smart-UPS 2200": 1700, "Smart-UPS 3000": 2700,
    "Smart-UPS 250": 160, "Smart-UPS 600": 390, "Smart-UPS 900": 580,
    "Smart-UPS 1250": 800, "Smart-UPS 2000": 1400,
}

MessageCallback = Callable[[str, str], None]  # (timestamp, message)


class UPSManager:
    """High-level orchestrator for UPS communication."""

    def __init__(self):
        self._conn = SerialConnection()
        self._protocol: UPSProtocol | None = None
        self.state = UPSState()
        self.calibration = CalibrationManager()

        # Polling control
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._poll_paused = threading.Event()
        self._poll_paused.set()  # Not paused initially

        # Command queue for user-initiated operations
        self._cmd_lock = threading.Lock()

        # Message/log callback
        self._message_callback: MessageCallback | None = None
        self._alert_callback: Callable[[str], None] | None = None

        # Rated wattage for load W computation
        self._rated_watts: float = 0.0

    def set_message_callback(self, callback: MessageCallback) -> None:
        self._message_callback = callback

    def set_alert_callback(self, callback: Callable[[str], None]) -> None:
        self._alert_callback = callback

    def _log_message(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        logger.info("[%s] %s", ts, message)
        if self._message_callback:
            self._message_callback(ts, message)

    def _handle_io(self, direction: str, data: str) -> None:
        """Handle protocol IO logging (called from protocol layer)."""
        self._log_message(f"{direction}: {data}")

    def _handle_alert(self, alert_char: str) -> None:
        desc = ALERT_DESCRIPTIONS.get(alert_char, f"Unknown alert: {alert_char!r}")
        self._log_message(f"ALERT: {desc}")
        if self._alert_callback:
            self._alert_callback(alert_char)

    def connect(self, port: str) -> bool:
        """Connect to UPS on the given serial port and enter Smart Mode.

        Returns True on success.
        """
        try:
            self._conn.open(port)
            self._protocol = UPSProtocol(
                self._conn,
                alert_callback=self._handle_alert,
                io_callback=self._handle_io,
            )

            if not self._protocol.enter_smart_mode():
                self._log_message(f"Failed to enter Smart Mode on {port}")
                self._conn.close()
                self.state.update(connected=False, last_error="Failed to enter Smart Mode")
                return False

            self.state.update(connected=True, port=port, smart_mode=True, last_error="")
            self._log_message(f"Connected to UPS on {port}")

            # Read all initial values
            self._read_initial_values()

            return True

        except Exception as e:
            self._log_message(f"Connection error: {e}")
            self.state.update(connected=False, last_error=str(e))
            try:
                self._conn.close()
            except Exception:
                pass
            return False

    def disconnect(self) -> None:
        """Stop polling and close the serial connection gracefully.

        Sets connected=False first to signal the poll thread to stop issuing
        new serial reads, then joins the thread, then closes the port.
        """
        # 1. Mark disconnected FIRST — poll thread checks this before each read
        self.state.update(connected=False, smart_mode=False)

        # 2. Stop the polling thread (sets stop event + joins with timeout)
        self.stop_polling()

        # 3. Close the serial port (flushes buffers, cancels pending reads)
        try:
            self._conn.close()
        except Exception:
            pass

        # 4. Clear protocol reference — prevents stale usage after close
        self._protocol = None

        self._log_message("Disconnected from UPS")

    def reconnect(self) -> bool:
        """Reconnect to the same port."""
        port = self.state.port
        if not port:
            return False
        self.disconnect()
        return self.connect(port)

    def _read_initial_values(self) -> None:
        """Read all one-time values after connecting."""
        for cmd_char in ONCE_CMDS:
            self._read_and_update(cmd_char)
        self._compute_load_watts()
        self._compute_battery_age()
        # Set pre-calibration constant
        self.calibration.set_pre_cal_constant(self.state.smart_constant_0)

    def _read_and_update(self, cmd_char: str) -> str | None:
        """Send a command and update the state with the response."""
        if not self._protocol:
            return None
        try:
            response = self._protocol.send_command(cmd_char)
            if response is not None:
                state_key = CMD_TO_STATE_KEY.get(cmd_char)
                if state_key:
                    if state_key in NUMERIC_FIELDS:
                        try:
                            # Handle runtime format "dddd:" by stripping ':'
                            clean = response.rstrip(":").strip()
                            value = float(clean)
                            self.state.update(**{state_key: value})
                        except ValueError:
                            logger.warning("Could not parse %r=%r as float",
                                           cmd_char, response)
                    else:
                        self.state.update(**{state_key: response})
            return response
        except Exception as e:
            logger.error("Error reading command %r: %s", cmd_char, e)
            return None

    def _compute_load_watts(self) -> None:
        """Compute load in watts from load% and model rating."""
        model = self.state.model
        for name, watts in MODEL_WATTAGE.items():
            if name in model:
                self._rated_watts = watts
                break
        if self._rated_watts > 0:
            load_w = (self.state.load_power / 100.0) * self._rated_watts
            self.state.update(load_watts=load_w)

    # --- Polling ---

    def start_polling(self) -> None:
        """Start the background polling thread."""
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_stop.clear()
        self._poll_paused.set()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self) -> None:
        """Stop the background polling thread."""
        self._poll_stop.set()
        self._poll_paused.set()  # Unpause so the thread can exit
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
            self._poll_thread = None

    def _pause_polling(self) -> None:
        """Pause polling while executing a user command."""
        self._poll_paused.clear()

    def _resume_polling(self) -> None:
        """Resume polling after a user command completes."""
        self._poll_paused.set()

    def _poll_loop(self) -> None:
        """Background polling loop with fast and slow rates."""
        slow_counter = 0
        while not self._poll_stop.is_set():
            # Wait if paused
            self._poll_paused.wait(timeout=1.0)
            if self._poll_stop.is_set():
                break

            if not self.state.connected:
                time.sleep(1.0)
                continue

            try:
                # Fast poll
                for cmd_char in FAST_POLL_CMDS:
                    if self._poll_stop.is_set():
                        return
                    self._poll_paused.wait(timeout=1.0)
                    if self._poll_stop.is_set():
                        return
                    self._read_and_update(cmd_char)

                self._compute_load_watts()
                self._record_battery_history()

                # Slow poll every ~10s (5 fast cycles * 2s ≈ 10s)
                slow_counter += 1
                if slow_counter >= 5:
                    slow_counter = 0
                    for cmd_char in SLOW_POLL_CMDS:
                        if self._poll_stop.is_set():
                            return
                        self._poll_paused.wait(timeout=1.0)
                        if self._poll_stop.is_set():
                            return
                        self._read_and_update(cmd_char)

                    # Temperature monitoring and battery age (on slow cycle)
                    self._check_temperature()
                    self._compute_battery_age()

            except Exception as e:
                logger.error("Poll error: %s", e)
                self.state.update(last_error=str(e))

            # Wait between poll cycles
            self._poll_stop.wait(timeout=2.0)

    # --- Setting Changes ---

    def change_setting(self, setting_key: str, target_value: str) -> tuple[bool, str]:
        """Change an editable setting to the target value.

        Pauses polling, runs the edit cycle, then resumes polling.
        Returns (success, message).
        """
        setting = SETTINGS.get(setting_key)
        if not setting:
            return False, f"Unknown setting: {setting_key}"
        if not self._protocol:
            return False, "Not connected"

        with self._cmd_lock:
            self._pause_polling()
            try:
                return self._execute_setting_change(setting, target_value)
            finally:
                self._resume_polling()

    def _execute_setting_change(self, setting: EditableSetting,
                                target_value: str) -> tuple[bool, str]:
        """Execute the actual setting change sequence."""
        cmd = setting.cmd_char

        if setting.direct_edit:
            # Battery packs: use decrement cycling (not direct char input)
            if cmd == ">":
                return self._execute_battery_packs_change(target_value)

            # Direct character input (UPS ID, battery date)
            response = self._protocol.send_direct_edit(cmd, target_value)
            if response and response.strip() == "OK":
                self.state.update(**{setting.state_key: target_value})
                self._log_message(
                    f"Changed {setting.name} to '{target_value}'")
                return True, "OK"
            elif response and response.strip() == "NO":
                return False, ("Edit disallowed by UPS — check DIP switch "
                               "positions or verify the value format")
            else:
                return False, f"UPS responded: {response}"

        # Read current value
        current = self._protocol.send_command(cmd)
        if current is None:
            return False, "Failed to read current value"

        old_value = current.strip()

        if old_value == target_value:
            return True, "Already set to target value"

        # Calculate number of edits needed
        steps = count_edits_needed(setting, old_value, target_value)
        if steps is None:
            return False, f"Value '{target_value}' not valid for {setting.name}"

        self._log_message(
            f"{setting.name}: {old_value} → {target_value} ({steps} edit steps)")

        # Execute edit cycles — per UPS-Link spec, each '-' must come
        # "directly following" the customizing command character
        for i in range(steps):
            current_val, edit_resp = self._protocol.send_setting_edit(cmd)
            if edit_resp is None:
                return False, f"Edit step {i+1}/{steps} failed — no response"
            resp = edit_resp.strip()
            if resp == "NA":
                return False, f"Edit rejected by UPS (NA) at step {i+1}/{steps}"
            if resp == "NO":
                return False, "Edit disallowed — check DIP switch positions"

        # Verify final value
        verify = self._protocol.send_command(cmd)
        if verify and verify.strip() == target_value:
            self.state.update(**{setting.state_key: target_value})
            self._log_message(
                f"Changed {setting.name}: {old_value} → {target_value}")
            return True, "OK"
        else:
            self._log_message(
                f"Setting change verification failed: expected {target_value}, "
                f"got {verify}")
            # Update state with whatever value we actually have
            if verify:
                self.state.update(**{setting.state_key: verify.strip()})
            return False, f"Verification failed — UPS reports: {verify}"

    def _execute_battery_packs_change(self, target_value: str) -> tuple[bool, str]:
        """Change battery packs using repeated > then +/- adjustments.

        Per the UPS-Link spec, the > command must be re-sent before each
        + or - adjustment. We use the shortest path (fewest steps).
        """
        try:
            target = int(target_value)
        except ValueError:
            return False, "Battery packs must be a number (0-255)"
        if target < 0 or target > 255:
            return False, "Battery packs must be 0-255"

        target_str = f"{target:03d}"

        # Read current value
        current_resp = self._protocol.send_command(">")
        if current_resp is None:
            return False, "Failed to read current battery packs value"

        try:
            current = int(current_resp.strip())
        except ValueError:
            return False, f"Invalid current value: {current_resp}"

        if current == target:
            return True, "Already set to target value"

        # Calculate shortest path: increment (+) or decrement (-)
        dec_steps = (current - target) % 256
        inc_steps = (target - current) % 256

        if inc_steps <= dec_steps:
            direction = "+"
            steps = inc_steps
        else:
            direction = "-"
            steps = dec_steps

        self._log_message(
            f"Battery packs: {current} → {target} "
            f"({steps} x '{direction}')")

        # Send > then +/- for each step
        for i in range(steps):
            response = self._protocol.send_battery_packs_adjust(direction)
            if response is None:
                return False, f"Step {i+1}/{steps} failed — no response"
            resp = response.strip()
            if resp in ("NA", "NO"):
                return False, f"Adjustment rejected at step {i+1}/{steps}: {resp}"

        # Verify final value
        verify = self._protocol.send_command(">")
        if verify and verify.strip() == target_str:
            self.state.update(battery_packs=target_str)
            self._log_message(
                f"Changed External Battery Packs: {current:03d} → {target_str}")
            return True, "OK"
        else:
            actual = verify.strip() if verify else "no response"
            self._log_message(
                f"Battery packs verification failed: expected {target_str}, got {actual}")
            if verify:
                self.state.update(battery_packs=actual)
            return False, f"Verification failed — UPS reports: {actual}"

    # --- Control Commands ---

    def run_self_test(self) -> tuple[bool, str]:
        """Run battery self-test (W command)."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("W")
                if response and response.strip() in ("OK", "*"):
                    self._log_message("Self-test initiated")
                    return True, "Self-test started"
                elif response and response.strip() == "NA":
                    return False, "Self-test not available right now"
                else:
                    return False, f"Unexpected response: {response}"
            finally:
                self._resume_polling()

    def test_lights_and_alarm(self) -> tuple[bool, str]:
        """Test LEDs and beeper (A command)."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("A")
                if response and response.strip() == "OK":
                    self._log_message("LED/Alarm test initiated")
                    return True, "Test started"
                else:
                    return False, f"Unexpected response: {response}"
            finally:
                self._resume_polling()

    def get_test_result(self) -> str:
        """Get last battery test result (X command)."""
        if not self._protocol:
            return "Not connected"
        response = self._protocol.send_command("X")
        if response:
            self.state.update(last_test_result=response.strip())
            return response.strip()
        return "No response"

    def simulate_power_failure(self) -> tuple[bool, str]:
        """Simulate power failure (U command)."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("U")
                if response and response.strip() in ("OK", "*"):
                    self._log_message("Power failure simulation started")
                    return True, "OK"
                else:
                    return False, f"Response: {response}"
            finally:
                self._resume_polling()

    # --- Calibration ---

    def start_calibration(self) -> tuple[bool, str]:
        """Start runtime calibration."""
        if not self._protocol:
            return False, "Not connected"

        can_start, reason = self.calibration.can_start(self.state.battery_capacity)
        if not can_start:
            return False, reason

        with self._cmd_lock:
            self._pause_polling()
            try:
                self.calibration.begin_check(self.state.battery_capacity)
                response = self._protocol.send_command("D")
                if response and response.strip() == "OK":
                    self.calibration.begin_running()
                    self._log_message("Runtime calibration started")
                    return True, "Calibration started"
                elif response and response.strip() == "NO":
                    self.calibration.fail("Battery not at 100%")
                    return False, "Battery must be at 100% to calibrate"
                else:
                    self.calibration.fail(f"Unexpected: {response}")
                    return False, f"Unexpected response: {response}"
            finally:
                self._resume_polling()

    def abort_calibration(self) -> tuple[bool, str]:
        """Abort a running calibration by sending 'D' again."""
        if not self._protocol:
            return False, "Not connected"
        if not self.calibration.is_active:
            return False, "No calibration in progress"

        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("D")
                self.calibration.abort()
                self._log_message("Runtime calibration aborted")
                return True, "Calibration aborted"
            finally:
                self._resume_polling()

    # --- Dangerous Power Commands ---

    def shutdown_turn_off_after_delay(self) -> tuple[bool, str]:
        """K(>1.5s)K — Turn off UPS after shutdown delay."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_timed_command("K")
                if response and response.strip() in ("OK", "*"):
                    self._log_message("Turn off after delay initiated")
                    return True, "UPS will turn off after shutdown delay"
                elif response and response.strip() == "NA":
                    return False, "Command conflicts with another operation"
                else:
                    return False, f"Response: {response}"
            finally:
                self._resume_polling()

    def shutdown_on_battery(self) -> tuple[bool, str]:
        """S — Shut down UPS on battery."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("S")
                if response and response.strip() in ("OK", "*"):
                    self._log_message("Shutdown on battery initiated")
                    return True, "UPS shutting down (will restart on utility power)"
                else:
                    return False, f"Response: {response}"
            finally:
                self._resume_polling()

    def shutdown_turn_off_immediate(self) -> tuple[bool, str]:
        """Z(>1.5s)Z — Turn off UPS immediately."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_timed_command("Z")
                if response and response.strip() in ("OK", "*"):
                    self._log_message("Immediate turn off initiated")
                    return True, "UPS turning off immediately"
                else:
                    return False, f"Response: {response}"
            finally:
                self._resume_polling()

    def abort_shutdown(self) -> tuple[bool, str]:
        """DEL — Abort a pending shutdown."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_abort_shutdown()
                self._log_message("Shutdown abort sent")
                return True, f"Abort sent (response: {response})"
            finally:
                self._resume_polling()

    def reset_eeprom(self) -> tuple[bool, str]:
        """z — Reset all EEPROM variables to factory defaults."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("z")
                if response and response.strip() == "CLEAR":
                    self._log_message("EEPROM reset to factory defaults")
                    # Re-read all settings
                    self._read_initial_values()
                    return True, "All settings reset to factory defaults"
                else:
                    return False, f"Response: {response}"
            finally:
                self._resume_polling()

    # --- Bypass ---

    def toggle_bypass(self) -> tuple[bool, str]:
        """^ — Toggle bypass mode."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                response = self._protocol.send_command("^")
                if response:
                    resp = response.strip()
                    if resp == "BYP":
                        self._log_message("Transferring to bypass mode")
                        return True, "Transferring to bypass mode"
                    elif resp == "INV":
                        self._log_message("Transferring to normal (inverter) mode")
                        return True, "Transferring to normal mode"
                    elif resp == "ERR":
                        return False, "Unable to switch bypass mode"
                    else:
                        return True, f"Response: {resp}"
                return False, "No response"
            finally:
                self._resume_polling()

    # --- Refresh ---

    def refresh_registers(self) -> None:
        """Force a re-read of all status registers."""
        if not self._protocol:
            return
        with self._cmd_lock:
            self._pause_polling()
            try:
                for cmd in ["Q", "~", "'", "8", "G", "X"]:
                    self._read_and_update(cmd)
            finally:
                self._resume_polling()

    def refresh_settings(self) -> None:
        """Force a re-read of all editable settings."""
        if not self._protocol:
            return
        with self._cmd_lock:
            self._pause_polling()
            try:
                for cmd in ["E", "c", "x", "u", "l", "e", "o", "s",
                            "q", "k", "p", "r", ">"]:
                    self._read_and_update(cmd)
            finally:
                self._resume_polling()

    # --- Battery History ---

    def _record_battery_history(self) -> None:
        """Record battery voltage and capacity for graphing.

        Called after each fast poll cycle (~2s). Keeps a rolling window
        of 1800 entries (about 1 hour at 2s intervals).
        """
        voltage = self.state.battery_voltage
        capacity = self.state.battery_capacity
        if voltage <= 0 and capacity <= 0:
            return

        now = datetime.now()
        history = self.state.battery_history
        history.append((now, voltage, capacity))
        if len(history) > 1800:
            self.state.battery_history = history[-1800:]

    # --- Temperature Monitoring ---

    def _check_temperature(self) -> None:
        """Check temperature against threshold and update history."""
        temp = self.state.temperature
        if temp <= 0:
            return

        # Record to history (keep last 360 entries ≈ 1 hour at 10s intervals)
        now = datetime.now()
        history = self.state.temperature_history
        history.append((now, temp))
        if len(history) > 360:
            self.state.temperature_history = history[-360:]

        # Check alert threshold
        threshold = self.state.temperature_alert_threshold
        was_active = self.state.temperature_alert_active
        is_over = temp >= threshold

        if is_over and not was_active:
            self.state.update(temperature_alert_active=True)
            self._log_message(
                f"WARNING: Temperature {temp:.1f}°C exceeds threshold {threshold:.1f}°C")
        elif not is_over and was_active:
            self.state.update(temperature_alert_active=False)
            self._log_message(
                f"Temperature {temp:.1f}°C returned below threshold {threshold:.1f}°C")

    def set_temperature_alert_threshold(self, threshold: float) -> None:
        """Set the temperature alert threshold in °C."""
        self.state.update(temperature_alert_threshold=threshold)
        self._log_message(f"Temperature alert threshold set to {threshold:.1f}°C")

    # --- Battery Age Tracking ---

    def _compute_battery_age(self) -> None:
        """Compute battery age in days from battery_replace_date."""
        date_str = self.state.battery_replace_date
        if not date_str or date_str == "---":
            self.state.update(battery_age_days=-1)
            return

        # Try parsing dd/mm/yy or mm/dd/yy
        for fmt in ("%m/%d/%y", "%d/%m/%y"):
            try:
                replace_date = datetime.strptime(date_str.strip(), fmt)
                age = (datetime.now() - replace_date).days
                self.state.update(battery_age_days=age)
                return
            except ValueError:
                continue

        self.state.update(battery_age_days=-1)

    # --- PROG Mode (Voltage Calibration) ---

    def enter_prog_mode(self) -> tuple[bool, str]:
        """Enter PROG mode for voltage calibration."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            self._pause_polling()
            try:
                success = self._protocol.enter_prog_mode()
                if success:
                    self._log_message("Entered PROG mode (service calibration)")
                    return True, "PROG mode active"
                else:
                    return False, "Failed to enter PROG mode"
            finally:
                if not success:
                    self._resume_polling()

    def prog_adjust(self, direction: str) -> tuple[bool, str]:
        """Adjust value in PROG mode. direction: '+' or '-'."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            try:
                response = self._protocol.send_prog_adjust(direction)
                if response is not None:
                    return True, response
                return False, "No response"
            except ValueError as e:
                return False, str(e)

    def prog_save(self) -> tuple[bool, str]:
        """Save adjusted value to EEPROM in PROG mode."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            try:
                response = self._protocol.send_prog_save()
                self._log_message("PROG mode: value saved to EEPROM")
                return True, f"Saved (response: {response})"
            except Exception as e:
                return False, str(e)

    def prog_read(self, cmd_char: str) -> tuple[bool, str]:
        """Read a value while in PROG mode."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            try:
                response = self._protocol.send_prog_read_command(cmd_char)
                if response is not None:
                    return True, response
                return False, "No response"
            except Exception as e:
                return False, str(e)

    def exit_prog_mode(self) -> tuple[bool, str]:
        """Exit PROG mode and resume normal operation."""
        if not self._protocol:
            return False, "Not connected"
        with self._cmd_lock:
            try:
                self._protocol.exit_prog_mode()
                self._log_message("Exited PROG mode")
                return True, "PROG mode exited"
            finally:
                self._resume_polling()

    # --- Voltage Comparison ---

    def get_voltage_comparison(self, external_input: float | None = None,
                               external_output: float | None = None,
                               external_battery: float | None = None
                               ) -> dict[str, tuple[float, float, float]]:
        """Compare UPS-reported voltages against external meter readings.

        Returns dict of {name: (ups_value, external_value, delta)}.
        """
        result = {}
        if external_input is not None:
            ups = self.state.input_voltage
            result["Input Voltage"] = (ups, external_input, ups - external_input)
        if external_output is not None:
            ups = self.state.output_voltage
            result["Output Voltage"] = (ups, external_output, ups - external_output)
        if external_battery is not None:
            ups = self.state.battery_voltage
            result["Battery Voltage"] = (ups, external_battery, ups - external_battery)
        return result
