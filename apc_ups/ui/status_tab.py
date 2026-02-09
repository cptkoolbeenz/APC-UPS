"""Registers & Log tab — register checkbox panels and alert message log."""

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from apc_ups.protocol.constants import (
    STATE_BITS, TRIP1_BITS, TRIP_BITS, STATUS_BITS, ALERT_DESCRIPTIONS,
)
from apc_ups.util.register_decoder import (
    decode_status, decode_state, decode_trip1, decode_trip,
)
from apc_ups.ui.tooltip import tip


# Full descriptions for register bit tooltips
_STATE_TIPS = {
    7: "UPS is in wakeup mode — performing a startup self-test\n"
       "that typically lasts less than 2 seconds.",
    6: "UPS is ready and will power the load when commanded\n"
       "by the user or when normal line voltage returns.",
    5: "UPS is in bypass mode due to manual bypass control.\n"
       "Load is powered directly from utility, NOT protected.",
    4: "UPS is returning from bypass mode back to normal\n"
       "online operation.",
    3: "UPS is in bypass mode as a result of a UPS-Link\n"
       "command or front-panel key press.",
    2: "UPS is transitioning into bypass mode due to a\n"
       "UPS-Link command or front-panel key press.",
    1: "UPS is in bypass due to an internal fault.\n"
       "Check the Trip and Trip1 registers for details.",
    0: "UPS is ready to power the load upon return of\n"
       "normal line power.",
}

_TRIP1_TIPS = {
    7: "Output voltage is out of acceptable range.\n"
       "Load may not be receiving correct voltage.",
    6: "Relay fault detected in SmartBoost or SmartTrim\n"
       "voltage regulation circuitry.",
    5: "UPS was commanded out of bypass mode but no\n"
       "batteries are attached.",
    4: "DC bus imbalance detected. UPS has transferred\n"
       "to bypass mode for protection.",
    3: "Output voltage select relay failure. UPS is in\n"
       "bypass mode.",
    2: "Bypass power supply has failed. Internal UPS\n"
       "subsystem error.",
    1: "Fan failure in the Isolation Unit.\n"
       "Risk of overheating.",
    0: "Fan failure in the Electronics Unit.\n"
       "UPS is in bypass to prevent overheating.",
}

_TRIP_TIPS = {
    7: "Internal temperature has exceeded safe operating\n"
       "limits. Check ventilation and ambient temperature.",
    6: "Bypass relay malfunction detected.\n"
       "UPS may not be able to transfer to bypass.",
    5: "Battery charger circuit failure. Batteries may\n"
       "not be charging — check battery health.",
    4: "UPS is in shutdown mode (initiated by 'S' command\n"
       "or graceful shutdown sequence).",
    3: "UPS is in sleep mode (initiated by '@ddd' command).\n"
       "Will wake after the programmed delay.",
    2: "Main relay malfunction. UPS output has been\n"
       "turned off for safety.",
    1: "UPS could not transfer to battery because the\n"
       "load exceeds the battery capacity.",
    0: "UPS output was unpowered because the battery\n"
       "reached critically low charge.",
}

_STATUS_TIPS = {
    7: "Battery has failed a self-test or reached end of life.\n"
       "Replace the battery as soon as possible.",
    6: "Battery charge is critically low. The UPS will\n"
       "shut down soon if power is not restored.",
    5: "Connected load exceeds the UPS rated capacity.\n"
       "Reduce load to avoid UPS shutdown.",
    4: "UPS is running on battery power. Utility power\n"
       "is absent or out of acceptable range.",
    3: "UPS is operating normally on utility (line) power.\n"
       "Load is protected.",
    2: "SmartBoost is active — UPS is boosting low input\n"
       "voltage to acceptable output levels.",
    1: "SmartTrim is active — UPS is trimming high input\n"
       "voltage down to acceptable output levels.",
    0: "A runtime calibration has been performed.\n"
       "Battery runtime estimate has been recalculated.",
}


class StatusTab(ttk.Frame):
    """The Registers & Log tab — register bit displays and message log."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager

        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_register_panels()
        self._build_message_log()

    def _build_register_panels(self):
        """Build the four register panels with checkboxes."""
        # Register 1 (State ~)
        self._state_vars = self._build_register_panel(
            "State Register (~)", STATE_BITS, row=0, col=0,
            short_labels={
                7: "In Wakeup mode.",
                6: "Ready to power load.",
                5: "In bypass. Manual control.",
                4: "Returning from bypass.",
                3: "In bypass. UPS-Link cmd.",
                2: "Going to bypass.",
                1: "In bypass. Int.fault.",
                0: "Ready. Return of line power.",
            },
            tips=_STATE_TIPS,
        )

        # Register 2 (Trip1 ')
        self._trip1_vars = self._build_register_panel(
            "Trip1 Register (')", TRIP1_BITS, row=0, col=1,
            short_labels={
                7: "Bad output voltage.",
                6: "Relay fault in Trim or Boost.",
                5: "Bypass supply failure.",
                4: "DC imbalance.",
                3: "Output voltage select failure.",
                2: "Bypass supply failure.",
                1: "Fan failure in isolation unit.",
                0: "Fan failure in electronics.",
            },
            tips=_TRIP1_TIPS,
        )

        # Register 3 (Trip 8)
        self._trip_vars = self._build_register_panel(
            "Trip Register (8)", TRIP_BITS, row=1, col=0,
            short_labels={
                7: "Temperature exceeded.",
                6: "Bypass relay malfunction.",
                5: "Battery charger failure.",
                4: "In shutdown mode.",
                3: "In sleep mode.",
                2: "Main relay malfunction.",
                1: "Overload. On battery failure.",
                0: "Shutdown by low battery.",
            },
            tips=_TRIP_TIPS,
        )

        # Status (Q)
        self._status_vars = self._build_register_panel(
            "Status Register (Q)", STATUS_BITS, row=1, col=1,
            short_labels={
                7: "Replace Battery.",
                6: "Battery Low.",
                5: "Overloaded Output.",
                4: "On Battery.",
                3: "On Line.",
                2: "SmartBoost mode.",
                1: "SmartTrim mode.",
                0: "Runtime calibration occurred.",
            },
            tips=_STATUS_TIPS,
        )

    def _build_register_panel(self, title: str, bit_map: dict[int, str],
                               row: int, col: int,
                               short_labels: dict[int, str] | None = None,
                               tips: dict[int, str] | None = None,
                               ) -> dict[int, tk.BooleanVar]:
        """Build a panel of checkboxes for a register.

        Returns a dict of {bit_num: BooleanVar}.
        """
        frame = ttk.LabelFrame(self, text=title, padding=5)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=2)

        vars_dict = {}
        labels = short_labels or {}
        tip_map = tips or {}

        for i, bit_num in enumerate(sorted(bit_map.keys(), reverse=True)):
            label = labels.get(bit_num, bit_map[bit_num])
            var = tk.BooleanVar(value=False)
            vars_dict[bit_num] = var
            cb = ttk.Checkbutton(frame, text=label, variable=var,
                                 state="disabled")  # Read-only
            cb.grid(row=i, column=0, sticky="w", pady=1)

            # Add tooltip with full description
            if bit_num in tip_map:
                tip(cb, tip_map[bit_num])

        return vars_dict

    def _build_message_log(self):
        """Build the message log at the bottom."""
        log_frame = ttk.LabelFrame(self, text="Event Log", padding=5)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew",
                       padx=5, pady=(2, 5))
        self.rowconfigure(2, weight=1)

        self._log_text = tk.Text(log_frame, height=6, state="disabled",
                                 font=("Consolas", 9), wrap="word",
                                 bg="#1a1a2e", fg="#00ff00")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical",
                                  command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)

        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tip(self._log_text,
            "Live event log showing UPS messages and async alerts.\n"
            "Alerts include power events, battery warnings, and faults.\n"
            "Timestamps are local system time.")

    def update_display(self, state_dict: dict):
        """Update register checkboxes from UPS state snapshot."""
        # State register (~)
        state_hex = state_dict.get("state_register", "00")
        state_flags = decode_state(state_hex)
        for bit_num, var in self._state_vars.items():
            label = STATE_BITS.get(bit_num, "")
            var.set(state_flags.get(label, False))

        # Trip1 register (')
        trip1_hex = state_dict.get("trip1_register", "00")
        trip1_flags = decode_trip1(trip1_hex)
        for bit_num, var in self._trip1_vars.items():
            label = TRIP1_BITS.get(bit_num, "")
            var.set(trip1_flags.get(label, False))

        # Trip register (8)
        trip_hex = state_dict.get("trip_register", "00")
        trip_flags = decode_trip(trip_hex)
        for bit_num, var in self._trip_vars.items():
            label = TRIP_BITS.get(bit_num, "")
            var.set(trip_flags.get(label, False))

        # Status register (Q)
        status_hex = state_dict.get("status_register", "00")
        status_flags = decode_status(status_hex)
        for bit_num, var in self._status_vars.items():
            label = STATUS_BITS.get(bit_num, "")
            var.set(status_flags.get(label, False))

    def add_message(self, timestamp: str, message: str):
        """Add a message to the log (called on main thread)."""
        self._log_text.config(state="normal")
        self._log_text.insert("end", f"[{timestamp}] {message}\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def add_alert(self, alert_char: str):
        """Add an async alert to the log."""
        desc = ALERT_DESCRIPTIONS.get(alert_char, f"Unknown: {alert_char!r}")
        ts = datetime.now().strftime("%H:%M:%S")
        self.add_message(ts, f"ALERT: {desc}")
