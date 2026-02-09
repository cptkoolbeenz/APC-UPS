"""Monitor tab — UPS identity, live readings, action buttons."""

import tkinter as tk
from tkinter import ttk, messagebox

from apc_ups.protocol.constants import BATTERY_AGE_WARNING_DAYS
from apc_ups.ui.tooltip import tip


# Tooltips for left-panel info fields
_INFO_TIPS = {
    "model": "UPS model name, read via Ctrl+A command.",
    "firmware": "3-character firmware code: model type, revision, voltage class.",
    "manufacture_date": "Date the UPS was manufactured (from EEPROM).",
    "battery_replace_date": "Date batteries were last replaced.\nEditable in the Settings tab.",
    "ups_id": "8-character user-assigned identifier.\nEditable in the Settings tab.",
    "serial_number": "Factory serial number (read-only).",
    "frequency": "Measured AC line frequency (Hz). Polled every ~10 seconds.",
    "temperature": "Internal UPS temperature (C). Polled every ~10 seconds.\n"
                   "Battery life halves for every 10 C above 25 C.",
    "nominal_battery_voltage": "Nominal battery system voltage (e.g. 24V, 48V).",
}

# Tooltips for right-panel voltage fields
_VOLTAGE_TIPS = {
    "battery_voltage_disp": "Present DC battery voltage. Polled every ~2 seconds.",
    "battery_packs_disp": "Number of external battery packs connected.\n"
                          "Affects runtime calculation. Editable in Settings tab.",
    "upper_xfer_disp": "Input voltage above which the UPS transfers to battery.\n"
                       "Editable in Settings tab.",
    "lower_xfer_disp": "Input voltage below which SmartBoost engages.\n"
                       "Editable in Settings tab.",
    "output_setting_disp": "Nominal output voltage when running on battery.\n"
                           "Editable in Settings tab.",
    "max_voltage_disp": "Maximum input voltage recorded since last read.\n"
                        "Resets each time it is polled.",
    "min_voltage_disp": "Minimum input voltage recorded since last read.\n"
                        "Resets each time it is polled.",
}


class MainTab(ttk.Frame):
    """The main UPS monitoring tab."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager

        # --- Layout: Left | Center | Right ---
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()
        self._build_bottom_panel()

    def _build_left_panel(self):
        """Left panel — UPS identity info."""
        frame = ttk.LabelFrame(self, text="UPS Identity", padding=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)

        self._info_vars = {}
        info_fields = [
            ("Model:", "model"),
            ("Firmware:", "firmware"),
            ("Manufactured:", "manufacture_date"),
            ("Battery Replaced:", "battery_replace_date"),
            ("UPS Name:", "ups_id"),
            ("Serial Number:", "serial_number"),
            ("Line Frequency:", "frequency"),
            ("Internal Temp:", "temperature"),
            ("Battery System:", "nominal_battery_voltage"),
        ]

        for i, (label_text, key) in enumerate(info_fields):
            lbl = ttk.Label(frame, text=label_text, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            if key in _INFO_TIPS:
                tip(lbl, _INFO_TIPS[key])

            var = tk.StringVar(value="---")
            self._info_vars[key] = var

            val_entry = ttk.Entry(frame, textvariable=var, state="readonly",
                                  width=20, font=("Consolas", 10, "bold"),
                                  justify="right")
            val_entry.grid(row=i, column=1, sticky="e", padx=(10, 0), pady=2)

        # Warning label
        warn_frame = ttk.Frame(frame)
        warn_frame.grid(row=len(info_fields), column=0, columnspan=2,
                        sticky="ew", pady=(10, 0))
        warn_lbl = ttk.Label(
            warn_frame,
            text="Changes to UPS settings affect\n"
                 "connected equipment. Use caution.",
            foreground="red", font=("TkDefaultFont", 9, "bold"),
            justify="center", anchor="center",
        )
        warn_lbl.pack(fill="x")
        tip(warn_lbl, "Incorrect settings can cause power loss to connected\n"
                      "equipment or damage to the UPS and batteries.")

    def _build_center_panel(self):
        """Center panel — live readings with progress bars."""
        frame = ttk.Frame(self, padding=8)
        frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=5)
        frame.columnconfigure(0, weight=1)

        # Firmware & Battery Constants
        const_frame = ttk.LabelFrame(frame, text="Firmware & Battery Constants",
                                     padding=5)
        const_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self._firmware_detail_var = tk.StringVar(value="---")
        fw_lbl = ttk.Label(const_frame, textvariable=self._firmware_detail_var,
                           font=("Consolas", 9))
        fw_lbl.grid(row=0, column=0, columnspan=8, sticky="w")
        tip(fw_lbl, "Firmware version code and decimal SKU identifier.")

        # Battery discharge constants
        self._const_vars = {}
        const_items = [
            ("0:", "sc_0", "Runtime constant. Reset to default before calibration."),
            ("4:", "sc_4", "Discharge curve parameter (low range). Model-specific."),
            ("5:", "sc_5", "Discharge curve parameter (mid range). Model-specific."),
            ("6:", "sc_6", "Discharge curve parameter (high range). Model-specific."),
        ]
        for col, (label, key, tooltip_text) in enumerate(const_items):
            lbl = ttk.Label(const_frame, text=label, font=("Consolas", 8))
            lbl.grid(row=1, column=col * 2, sticky="e", padx=(4, 0))
            tip(lbl, tooltip_text)
            var = tk.StringVar(value="---")
            self._const_vars[key] = var
            val = ttk.Label(const_frame, textvariable=var,
                            font=("Consolas", 8, "bold"))
            val.grid(row=1, column=col * 2 + 1, sticky="w", padx=(0, 4))
            tip(val, tooltip_text)

        # Temperature alert banner (hidden by default)
        self._temp_alert_frame = tk.Frame(frame, bg="#FF3333", padx=4, pady=2)
        self._temp_alert_var = tk.StringVar(value="")
        self._temp_alert_label = tk.Label(
            self._temp_alert_frame, textvariable=self._temp_alert_var,
            bg="#FF3333", fg="white", font=("TkDefaultFont", 9, "bold"))
        self._temp_alert_label.pack()

        # Battery age warning banner (hidden by default)
        self._batt_age_frame = tk.Frame(frame, bg="#FFD700", padx=4, pady=2)
        self._batt_age_var = tk.StringVar(value="")
        self._batt_age_label = tk.Label(
            self._batt_age_frame, textvariable=self._batt_age_var,
            bg="#FFD700", fg="black", font=("TkDefaultFont", 9, "bold"))
        self._batt_age_label.pack()

        # Estimated Runtime (row 3 — rows 1,2 reserved for alert banners)
        rt_frame = ttk.LabelFrame(frame, text="Estimated Runtime", padding=5)
        rt_frame.grid(row=3, column=0, sticky="ew", pady=5)
        self._runtime_var = tk.StringVar(value="0   Min.")
        rt_lbl = ttk.Label(rt_frame, textvariable=self._runtime_var,
                           font=("Consolas", 14, "bold"), anchor="center")
        rt_lbl.pack(fill="x")
        tip(rt_lbl, "Estimated minutes of battery runtime remaining\n"
                    "at the current load level. Polled every ~10 seconds.")

        # Battery Charge Level
        batt_frame = ttk.LabelFrame(frame, text="Battery Charge Level", padding=5)
        batt_frame.grid(row=4, column=0, sticky="ew", pady=5)
        self._battery_bar = ttk.Progressbar(batt_frame, length=200,
                                            mode="determinate", maximum=100)
        self._battery_bar.pack(fill="x")
        self._battery_pct_var = tk.StringVar(value="0.0%")
        batt_lbl = ttk.Label(batt_frame, textvariable=self._battery_pct_var,
                             font=("Consolas", 12, "bold"), anchor="center")
        batt_lbl.pack(fill="x")
        tip(batt_lbl, "Remaining battery capacity as percentage.\n"
                      "Must be 100% to start runtime calibration.")

        # Load / Input / Output in a row
        readings_frame = ttk.Frame(frame)
        readings_frame.grid(row=5, column=0, sticky="ew", pady=5)
        readings_frame.columnconfigure((0, 1, 2), weight=1)

        # Load
        load_frame = ttk.LabelFrame(readings_frame, text="Output Load",
                                    padding=5)
        load_frame.grid(row=0, column=0, sticky="nsew", padx=2)
        self._load_bar = ttk.Progressbar(load_frame, orient="vertical",
                                         length=100, mode="determinate",
                                         maximum=100)
        self._load_bar.pack()
        self._load_pct_var = tk.StringVar(value="0.0 %")
        load_pct = ttk.Label(load_frame, textvariable=self._load_pct_var,
                             font=("Consolas", 10, "bold"))
        load_pct.pack()
        tip(load_pct, "Output load as percentage of rated power capacity.")
        self._load_watts_var = tk.StringVar(value="0 W")
        load_w = ttk.Label(load_frame, textvariable=self._load_watts_var,
                           font=("Consolas", 10))
        load_w.pack()
        tip(load_w, "Estimated load in watts (computed from load %\n"
                    "and the model's rated wattage).")

        # Input Voltage
        input_frame = ttk.LabelFrame(readings_frame, text="Input Voltage",
                                     padding=5)
        input_frame.grid(row=0, column=1, sticky="nsew", padx=2)
        self._input_bar = ttk.Progressbar(input_frame, orient="vertical",
                                          length=100, mode="determinate",
                                          maximum=300)
        self._input_bar.pack()
        self._input_var = tk.StringVar(value="0.0 V")
        inp_lbl = ttk.Label(input_frame, textvariable=self._input_var,
                            font=("Consolas", 10, "bold"))
        inp_lbl.pack()
        tip(inp_lbl, "Measured AC input (mains) voltage.\n"
                     "Polled every ~2 seconds.")

        # Output Voltage
        output_frame = ttk.LabelFrame(readings_frame, text="Output Voltage",
                                      padding=5)
        output_frame.grid(row=0, column=2, sticky="nsew", padx=2)
        self._output_var = tk.StringVar(value="0.0 V")
        out_lbl = ttk.Label(output_frame, textvariable=self._output_var,
                            font=("Consolas", 14, "bold"), anchor="center")
        out_lbl.pack(fill="x", pady=20)
        tip(out_lbl, "Measured AC output voltage to connected equipment.\n"
                     "Polled every ~2 seconds.")

    def _build_right_panel(self):
        """Right panel — voltage thresholds and battery info."""
        frame = ttk.LabelFrame(self, text="Voltage & Battery Details",
                               padding=8)
        frame.grid(row=0, column=2, sticky="nsew", padx=(2, 5), pady=5)

        right_fields = [
            ("Battery Voltage:", "battery_voltage_disp", "V"),
            ("Battery Packs:", "battery_packs_disp", ""),
            ("Upper Transfer:", "upper_xfer_disp", "V"),
            ("Lower Transfer:", "lower_xfer_disp", "V"),
            ("Output Setting:", "output_setting_disp", "V"),
            ("Peak Input:", "max_voltage_disp", "V"),
            ("Lowest Input:", "min_voltage_disp", "V"),
        ]

        self._right_vars = {}
        for i, (label_text, key, unit) in enumerate(right_fields):
            lbl = ttk.Label(frame, text=label_text, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            if key in _VOLTAGE_TIPS:
                tip(lbl, _VOLTAGE_TIPS[key])
            var = tk.StringVar(value="---")
            self._right_vars[key] = var
            val_entry = ttk.Entry(frame, textvariable=var, state="readonly",
                                  width=8, font=("Consolas", 10, "bold"),
                                  justify="right")
            val_entry.grid(row=i, column=1, sticky="e", padx=(5, 0), pady=2)
            if key in _VOLTAGE_TIPS:
                tip(val_entry, _VOLTAGE_TIPS[key])
            if unit:
                ttk.Label(frame, text=unit).grid(
                    row=i, column=2, sticky="w", padx=(2, 0))

        # Voltage comparison button
        self.btn_voltage_compare = ttk.Button(
            frame, text="Meter Comparison",
            command=self._on_voltage_compare)
        self.btn_voltage_compare.grid(
            row=len(right_fields), column=0, columnspan=3,
            sticky="ew", pady=(10, 0))
        tip(self.btn_voltage_compare,
            "Compare UPS voltage readings against an external\n"
            "voltmeter to verify measurement accuracy.\n"
            "Enter your meter readings and see the difference.")

    def _build_bottom_panel(self):
        """Bottom panel — action buttons."""
        frame = ttk.Frame(self, padding=5)
        frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 5))

        self.btn_self_test = ttk.Button(frame, text="Run Battery Test",
                                        command=self._on_self_test)
        self.btn_self_test.pack(side="left", padx=5)
        tip(self.btn_self_test,
            "Run an automatic battery self-test (~8 seconds).\n"
            "The UPS briefly switches to battery power and back.\n"
            "Result appears in the Registers & Log tab.")

        self.btn_led_test = ttk.Button(frame, text="Test Indicators",
                                       command=self._on_led_test)
        self.btn_led_test.pack(side="left", padx=5)
        tip(self.btn_led_test,
            "Flash all front-panel LEDs and sound the beeper\n"
            "for about 2 seconds. Safe diagnostic check.")

        self.btn_bypass = ttk.Button(frame, text="Toggle Bypass",
                                     command=self._on_bypass)
        self.btn_bypass.pack(side="left", padx=5)
        tip(self.btn_bypass,
            "Switch between normal and bypass mode.\n"
            "In BYPASS mode, the load is fed directly from mains\n"
            "and the UPS is NOT protecting connected equipment.")

        # Transfer cause display
        self._transfer_cause_var = tk.StringVar(value="")
        tc_lbl = ttk.Label(frame, textvariable=self._transfer_cause_var,
                           font=("Consolas", 9))
        tc_lbl.pack(side="right", padx=10)
        tip(tc_lbl, "Reason the UPS last transferred to battery power.")

    def _on_self_test(self):
        self.manager.run_self_test()

    def _on_led_test(self):
        self.manager.test_lights_and_alarm()

    def _on_bypass(self):
        self.manager.toggle_bypass()

    def _on_voltage_compare(self):
        """Open voltage comparison dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Meter Comparison — UPS vs External Voltmeter")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame,
                  text="Enter your external voltmeter readings below.\n"
                       "The delta shows how much the UPS reading differs.",
                  wraplength=400, foreground="gray40").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        entries = {}
        fields = [
            ("Input Voltage (V):", "input", self.manager.state.input_voltage),
            ("Output Voltage (V):", "output", self.manager.state.output_voltage),
            ("Battery Voltage (V):", "battery", self.manager.state.battery_voltage),
        ]
        for i, (label, key, ups_val) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i+1, column=0, sticky="w",
                                              pady=3)
            ttk.Label(frame, text=f"UPS: {ups_val:.1f}",
                      font=("Consolas", 9)).grid(row=i+1, column=1, padx=5,
                                                 pady=3)
            entry = ttk.Entry(frame, width=10)
            entry.grid(row=i+1, column=2, padx=5, pady=3)
            entries[key] = entry

        result_var = tk.StringVar(value="")
        result_label = ttk.Label(frame, textvariable=result_var,
                                 font=("Consolas", 9), foreground="blue")
        result_label.grid(row=len(fields)+1, column=0, columnspan=3,
                          sticky="w", pady=(10, 0))

        def do_compare():
            ext_in = ext_out = ext_bat = None
            try:
                v = entries["input"].get().strip()
                if v:
                    ext_in = float(v)
            except ValueError:
                pass
            try:
                v = entries["output"].get().strip()
                if v:
                    ext_out = float(v)
            except ValueError:
                pass
            try:
                v = entries["battery"].get().strip()
                if v:
                    ext_bat = float(v)
            except ValueError:
                pass

            comparison = self.manager.get_voltage_comparison(
                ext_in, ext_out, ext_bat)
            if not comparison:
                result_var.set("Enter at least one meter reading.")
                return
            lines = []
            for name, (ups, ext, delta) in comparison.items():
                sign = "+" if delta >= 0 else ""
                lines.append(
                    f"{name}: UPS={ups:.1f}  Meter={ext:.1f}"
                    f"  Delta={sign}{delta:.1f}")
            result_var.set("\n".join(lines))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields)+2, column=0, columnspan=3, pady=(10, 0))
        ttk.Button(btn_frame, text="Calculate Delta",
                   command=do_compare).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close",
                   command=dialog.destroy).pack(side="left", padx=5)

    def update_display(self, state_dict: dict):
        """Update all display elements from a UPS state snapshot."""
        # Identity info
        info_map = {
            "model": "model",
            "firmware": "firmware",
            "manufacture_date": "manufacture_date",
            "battery_replace_date": "battery_replace_date",
            "ups_id": "ups_id",
            "serial_number": "serial_number",
        }
        for var_key, state_key in info_map.items():
            if var_key in self._info_vars:
                self._info_vars[var_key].set(
                    state_dict.get(state_key, "---"))

        # Frequency with unit
        freq = state_dict.get("frequency", 0)
        if freq:
            self._info_vars["frequency"].set(f"{freq:.2f}  Hz")

        # Temperature with unit
        temp = state_dict.get("temperature", 0)
        if temp:
            self._info_vars["temperature"].set(f"{temp:.1f}  C")

        # Battery voltage
        nom_v = state_dict.get("nominal_battery_voltage", "")
        if nom_v:
            self._info_vars["nominal_battery_voltage"].set(f"{nom_v}  V")

        # Firmware detail
        fw = state_dict.get("firmware", "")
        fw_dec = state_dict.get("firmware_decimal", "")
        if fw:
            self._firmware_detail_var.set(f"{fw}  {fw_dec}")

        # Smart constants (battery discharge curve)
        for suffix in ("0", "4", "5", "6"):
            val = state_dict.get(f"smart_constant_{suffix}", "")
            self._const_vars[f"sc_{suffix}"].set(val if val else "---")

        # Temperature alert (row 1 in center panel)
        if state_dict.get("temperature_alert_active", False):
            temp = state_dict.get("temperature", 0)
            threshold = state_dict.get("temperature_alert_threshold", 40)
            self._temp_alert_var.set(
                f"TEMP WARNING: {temp:.1f} C (threshold: {threshold:.1f} C)")
            if not self._temp_alert_frame.winfo_ismapped():
                self._temp_alert_frame.grid(row=1, column=0, sticky="ew",
                                            pady=2)
        else:
            if self._temp_alert_frame.winfo_ismapped():
                self._temp_alert_frame.grid_remove()

        # Battery age warning (row 2 in center panel)
        age_days = state_dict.get("battery_age_days", -1)
        if age_days >= BATTERY_AGE_WARNING_DAYS:
            years = age_days / 365.25
            self._batt_age_var.set(
                f"Battery age: {years:.1f} years -- consider replacement")
            if not self._batt_age_frame.winfo_ismapped():
                self._batt_age_frame.grid(row=2, column=0, sticky="ew",
                                          pady=2)
        else:
            if self._batt_age_frame.winfo_ismapped():
                self._batt_age_frame.grid_remove()

        # Runtime
        rt = state_dict.get("runtime_remaining", 0)
        self._runtime_var.set(f"{int(rt)}   Min.")

        # Battery
        batt = state_dict.get("battery_capacity", 0)
        self._battery_bar["value"] = batt
        self._battery_pct_var.set(f"{batt:.1f}%")

        # Load
        load = state_dict.get("load_power", 0)
        self._load_bar["value"] = load
        self._load_pct_var.set(f"{load:.1f} %")
        load_w = state_dict.get("load_watts", 0)
        self._load_watts_var.set(f"{int(load_w)} W")

        # Input voltage
        inv = state_dict.get("input_voltage", 0)
        self._input_bar["value"] = inv
        self._input_var.set(f"{inv:.1f} V")

        # Output voltage
        outv = state_dict.get("output_voltage", 0)
        self._output_var.set(f"{outv:.1f} V")

        # Right panel
        bv = state_dict.get("battery_voltage", 0)
        self._right_vars["battery_voltage_disp"].set(
            f"{bv:.2f}" if bv else "---")
        self._right_vars["battery_packs_disp"].set(
            state_dict.get("battery_packs", "000"))
        self._right_vars["upper_xfer_disp"].set(
            state_dict.get("upper_transfer_voltage", "---"))
        self._right_vars["lower_xfer_disp"].set(
            state_dict.get("lower_transfer_voltage", "---"))
        self._right_vars["output_setting_disp"].set(
            state_dict.get("output_voltage_setting", "---"))
        maxv = state_dict.get("max_line_voltage", 0)
        self._right_vars["max_voltage_disp"].set(
            f"{maxv:.1f}" if maxv else "---")
        minv = state_dict.get("min_line_voltage", 0)
        self._right_vars["min_voltage_disp"].set(
            f"{minv:.1f}" if minv else "---")

        # Transfer cause
        tc = state_dict.get("transfer_cause", "")
        from apc_ups.protocol.constants import TRANSFER_CAUSE
        tc_desc = TRANSFER_CAUSE.get(tc, tc)
        self._transfer_cause_var.set(
            f"Last transfer: {tc_desc}" if tc else "")

    def set_buttons_enabled(self, enabled: bool):
        """Enable or disable action buttons."""
        state = "normal" if enabled else "disabled"
        self.btn_self_test.config(state=state)
        self.btn_led_test.config(state=state)
        self.btn_bypass.config(state=state)
        self.btn_voltage_compare.config(state=state)
