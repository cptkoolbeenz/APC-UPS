"""Data model holding all current UPS values."""

import threading
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UPSState:
    """Holds all current UPS readings, settings, and connection state.

    Updated atomically by the poller thread, read by the UI.
    """
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Connection state
    connected: bool = False
    port: str = ""
    smart_mode: bool = False
    last_error: str = ""

    # Identity (read once)
    model: str = ""
    firmware: str = ""
    firmware_decimal: str = ""
    serial_number: str = ""
    manufacture_date: str = ""
    copyright_str: str = ""
    nominal_battery_voltage: str = ""

    # Live readings (fast poll)
    battery_capacity: float = 0.0       # %
    battery_voltage: float = 0.0        # V
    load_power: float = 0.0             # %
    input_voltage: float = 0.0          # V
    output_voltage: float = 0.0         # V
    status_register: str = "00"         # hex

    # Live readings (slow poll)
    temperature: float = 0.0            # °C
    frequency: float = 0.0             # Hz
    runtime_remaining: float = 0.0      # minutes
    max_line_voltage: float = 0.0       # V
    min_line_voltage: float = 0.0       # V

    # Status registers
    state_register: str = "00"          # ~ command
    trip1_register: str = "00"          # ' command
    trip_register: str = "00"           # 8 command
    dip_switch: str = "00"              # 7 command

    # Status info
    transfer_cause: str = ""
    last_test_result: str = ""
    battery_packs: str = "000"
    bad_battery_packs: str = "000"

    # Editable settings (current values)
    self_test_interval: str = ""        # E command
    ups_id: str = ""                    # c command
    battery_replace_date: str = ""      # x command
    upper_transfer_voltage: str = ""    # u command
    lower_transfer_voltage: str = ""    # l command
    min_battery_restart: str = ""       # e command
    output_voltage_setting: str = ""    # o command
    sensitivity: str = ""               # s command
    low_battery_warning: str = ""       # q command
    alarm_control: str = ""             # k command
    shutdown_delay: str = ""            # p command
    turn_on_delay: str = ""             # r command

    # Smart constants (undocumented battery discharge parameters)
    smart_constant_0: str = ""   # Runtime constant
    smart_constant_4: str = ""   # Discharge curve (low)
    smart_constant_5: str = ""   # Discharge curve (mid)
    smart_constant_6: str = ""   # Discharge curve (high)

    # Load in watts (computed from load% and model rating)
    load_watts: float = 0.0

    # History for graphing (rolling window)
    battery_history: list = field(default_factory=list)  # [(datetime, voltage, capacity)]
    temperature_history: list = field(default_factory=list)  # [(datetime, float)]
    temperature_alert_threshold: float = 40.0  # °C
    temperature_alert_active: bool = False

    # Battery age tracking
    battery_age_days: int = -1  # -1 = unknown

    # Timestamp of last successful update
    last_update: datetime | None = None

    def update(self, **kwargs) -> None:
        """Thread-safe update of multiple fields at once."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.last_update = datetime.now()

    def snapshot(self) -> dict:
        """Return a thread-safe copy of all state as a dict."""
        with self._lock:
            return {k: v for k, v in self.__dict__.items()
                    if not k.startswith("_")}
