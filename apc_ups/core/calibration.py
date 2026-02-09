"""Battery runtime calibration state machine."""

from enum import Enum, auto


class CalibrationState(Enum):
    IDLE = auto()
    CHECKING = auto()    # Verifying battery is at 100%
    RUNNING = auto()     # Calibration in progress
    COMPLETED = auto()
    FAILED = auto()
    ABORTED = auto()


class CalibrationManager:
    """Manages the battery runtime calibration lifecycle.

    The calibration procedure:
    1. IDLE -> CHECKING: Verify battery is at 100%
    2. CHECKING -> RUNNING: Send 'D' command, expect 'OK'
    3. RUNNING: Poll battery% every second, track progress
    4. RUNNING -> COMPLETED: Calibration finishes when UPS stops it (battery at ~25%)
    5. RUNNING -> ABORTED: User sends 'D' again to abort
    6. CHECKING/RUNNING -> FAILED: If UPS returns 'NO' or error occurs
    """

    def __init__(self):
        self.state = CalibrationState.IDLE
        self.start_battery_pct: float = 0.0
        self.current_battery_pct: float = 0.0
        self.error_message: str = ""
        self.smart_constant_0: str = ""  # Battery constant before calibration
        self.constant_0_warning: str = ""  # Warning if non-default

    def can_start(self, battery_pct: float) -> tuple[bool, str]:
        """Check if calibration can start.

        Returns (can_start, reason_if_not).
        """
        if self.state != CalibrationState.IDLE:
            return False, f"Calibration already in state: {self.state.name}"
        if battery_pct < 100.0:
            return False, f"Battery must be at 100% to calibrate (currently {battery_pct}%)"
        return True, ""

    def set_pre_cal_constant(self, constant_0: str, default_value: str = "") -> None:
        """Record the battery constant 0 value for pre-calibration check.

        If default_value is provided and constant_0 differs, sets a warning.
        """
        self.smart_constant_0 = constant_0
        if default_value and constant_0 and constant_0 != default_value:
            self.constant_0_warning = (
                f"Battery constant 0 is '{constant_0}' (default: '{default_value}'). "
                f"Consider resetting to default before calibration."
            )
        else:
            self.constant_0_warning = ""

    def begin_check(self, battery_pct: float) -> None:
        """Transition to CHECKING state."""
        self.state = CalibrationState.CHECKING
        self.start_battery_pct = battery_pct
        self.current_battery_pct = battery_pct
        self.error_message = ""

    def begin_running(self) -> None:
        """Transition to RUNNING after 'D' command returned 'OK'."""
        self.state = CalibrationState.RUNNING

    def update_progress(self, battery_pct: float) -> None:
        """Update current battery percentage during calibration."""
        self.current_battery_pct = battery_pct

    def complete(self) -> None:
        """Mark calibration as completed."""
        self.state = CalibrationState.COMPLETED

    def abort(self) -> None:
        """Mark calibration as aborted by user."""
        self.state = CalibrationState.ABORTED

    def fail(self, message: str) -> None:
        """Mark calibration as failed."""
        self.state = CalibrationState.FAILED
        self.error_message = message

    def reset(self) -> None:
        """Reset to IDLE for next calibration."""
        self.state = CalibrationState.IDLE
        self.start_battery_pct = 0.0
        self.current_battery_pct = 0.0
        self.error_message = ""
        self.smart_constant_0 = ""
        self.constant_0_warning = ""

    @property
    def progress_pct(self) -> float:
        """Estimated progress as percentage (100% -> 25% maps to 0% -> 100%)."""
        if self.state != CalibrationState.RUNNING:
            return 0.0
        # Calibration runs from 100% down to ~25%
        range_total = 75.0  # 100% - 25%
        used = self.start_battery_pct - self.current_battery_pct
        if range_total <= 0:
            return 0.0
        return min(100.0, max(0.0, (used / range_total) * 100.0))

    @property
    def is_active(self) -> bool:
        return self.state in (CalibrationState.CHECKING, CalibrationState.RUNNING)
