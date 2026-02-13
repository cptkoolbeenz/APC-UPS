"""Service tab — PROG mode voltage calibration, temperature settings, calibration pre-checks."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser

from apc_ups.protocol.constants import DEFAULT_TEMP_ALERT_THRESHOLD
from apc_ups.protocol.ups_constants import (
    lookup_model, get_factory_defaults, SOURCE_URL,
)
from apc_ups.ui.tooltip import tip


class ServiceTab(ttk.Frame):
    """Service tab for advanced diagnostics and calibration tools.

    Features:
    - PROG mode voltage calibration (undocumented service mode)
    - Temperature alert threshold configuration
    - Calibration pre-check display (battery constant 0)
    """

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self._prog_mode_active = False

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_prog_panel()
        self._build_temp_panel()
        self._build_cal_panel()
        self._build_warning()

    def _build_prog_panel(self):
        """Build the PROG mode calibration panel."""
        frame = ttk.LabelFrame(self, text="Voltage Calibration (PROG Mode)",
                               padding=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Warning
        warn = tk.Frame(frame, bg="#FF3333", padx=4, pady=2)
        warn.pack(fill="x", pady=(0, 8))
        tk.Label(warn, text="SERVICE MODE: Incorrect calibration can damage equipment!",
                 bg="#FF3333", fg="white",
                 font=("TkDefaultFont", 8, "bold")).pack()

        # Description
        desc_lbl = ttk.Label(
            frame,
            text="Adjusts internal voltage measurement calibration.\n"
                 "Use an external voltmeter as reference.",
            wraplength=300, foreground="gray40")
        desc_lbl.pack(anchor="w", pady=(0, 5))
        tip(desc_lbl,
            "PROG mode is an undocumented APC service mode that\n"
            "allows fine-tuning voltage readings stored in EEPROM.\n"
            "Sequence: Enter > Read > Adjust +/- > Save > Exit.\n"
            "Always compare against a calibrated external meter.")

        # Command selector
        cmd_frame = ttk.Frame(frame)
        cmd_frame.pack(fill="x", pady=3)
        ttk.Label(cmd_frame, text="Measurement:").pack(side="left")
        self._prog_cmd_var = tk.StringVar(value="L")
        cmd_combo = ttk.Combobox(cmd_frame, textvariable=self._prog_cmd_var,
                                 values=["L", "O", "B"], width=5, state="readonly")
        cmd_combo.pack(side="left", padx=5)
        tip(cmd_combo,
            "Select which voltage to read/calibrate:\n"
            "L = Input (line) voltage\n"
            "O = Output voltage\n"
            "B = Battery voltage")
        cmd_hint = ttk.Label(cmd_frame, text="(L=Input, O=Output, B=Battery)")
        cmd_hint.pack(side="left")

        # Current reading display
        self._prog_reading_var = tk.StringVar(value="---")
        reading_entry = ttk.Entry(frame, textvariable=self._prog_reading_var,
                                  state="readonly", font=("Consolas", 14, "bold"),
                                  justify="center")
        reading_entry.pack(fill="x", pady=5)
        tip(reading_entry,
            "Current voltage reading from the UPS in PROG mode.\n"
            "Compare this value with your external voltmeter.")

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)

        self._btn_prog_enter = ttk.Button(btn_frame, text="Enter PROG",
                                           command=self._on_enter_prog)
        self._btn_prog_enter.pack(side="left", padx=3)
        tip(self._btn_prog_enter,
            "Enter PROG calibration mode.\n"
            "Sends '1', waits 4 seconds, sends '1' again.\n"
            "Polling is paused while in PROG mode.")

        self._btn_prog_plus = ttk.Button(btn_frame, text="Nudge +",
                                          command=lambda: self._on_prog_adjust("+"),
                                          state="disabled", width=7)
        self._btn_prog_plus.pack(side="left", padx=3)
        tip(self._btn_prog_plus,
            "Increase the calibration value by one step.\n"
            "Read the voltage after each nudge to check progress.")

        self._btn_prog_minus = ttk.Button(btn_frame, text="Nudge -",
                                           command=lambda: self._on_prog_adjust("-"),
                                           state="disabled", width=7)
        self._btn_prog_minus.pack(side="left", padx=3)
        tip(self._btn_prog_minus,
            "Decrease the calibration value by one step.\n"
            "Read the voltage after each nudge to check progress.")

        self._btn_prog_read = ttk.Button(btn_frame, text="Read",
                                          command=self._on_prog_read,
                                          state="disabled")
        self._btn_prog_read.pack(side="left", padx=3)
        tip(self._btn_prog_read,
            "Read the current voltage value from the UPS.\n"
            "Uses the measurement type selected above (L/O/B).")

        self._btn_prog_save = ttk.Button(btn_frame, text="Save to EEPROM",
                                          command=self._on_prog_save,
                                          state="disabled")
        self._btn_prog_save.pack(side="left", padx=3)
        tip(self._btn_prog_save,
            "Write the adjusted calibration value to EEPROM.\n"
            "This change is permanent and survives power cycles.\n"
            "Sends the 'R' (Record) command in PROG mode.")

        self._btn_prog_exit = ttk.Button(btn_frame, text="Exit PROG",
                                          command=self._on_exit_prog,
                                          state="disabled")
        self._btn_prog_exit.pack(side="left", padx=3)
        tip(self._btn_prog_exit,
            "Exit PROG mode and return to normal operation.\n"
            "Sends ESC (0x1B). Unsaved changes are discarded.\n"
            "Polling will resume automatically.")

    def _build_temp_panel(self):
        """Build the temperature alert configuration panel."""
        frame = ttk.LabelFrame(self, text="Temperature Monitoring", padding=8)
        frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        desc_lbl = ttk.Label(
            frame,
            text="Monitor internal UPS temperature and set an\n"
                 "alert threshold for overheating warnings.",
            wraplength=300, foreground="gray40")
        desc_lbl.pack(anchor="w", pady=(0, 8))
        tip(desc_lbl,
            "The UPS reports its internal temperature via the 'C' command.\n"
            "High temperatures (above ~40 C) reduce battery life.\n"
            "Session history tracks up to 360 readings (1 hour at 10s intervals).")

        # Current temperature display
        self._temp_display_var = tk.StringVar(value="Current: ---")
        temp_entry = ttk.Entry(frame, textvariable=self._temp_display_var,
                               state="readonly", font=("Consolas", 12, "bold"),
                               width=18)
        temp_entry.pack(anchor="w", pady=3)
        tip(temp_entry, "Current internal UPS temperature in degrees Celsius.")

        # Threshold setting
        thresh_frame = ttk.Frame(frame)
        thresh_frame.pack(fill="x", pady=5)
        thresh_lbl = ttk.Label(thresh_frame, text="Alert threshold:")
        thresh_lbl.pack(side="left")
        tip(thresh_lbl,
            "Temperature (in Celsius) above which a warning\n"
            "banner appears on the Monitor tab.")
        self._temp_threshold_var = tk.StringVar(
            value=str(DEFAULT_TEMP_ALERT_THRESHOLD))
        self._temp_threshold_entry = ttk.Entry(
            thresh_frame, textvariable=self._temp_threshold_var, width=6)
        self._temp_threshold_entry.pack(side="left", padx=5)
        tip(self._temp_threshold_entry,
            "Enter a value between 0 and 100.\n"
            "Default is 40 C. APC recommends keeping below 45 C.")
        ttk.Label(thresh_frame, text="C").pack(side="left")

        self._btn_set_threshold = ttk.Button(
            frame, text="Apply Threshold",
            command=self._on_set_threshold)
        self._btn_set_threshold.pack(anchor="w", pady=5)
        tip(self._btn_set_threshold,
            "Apply the temperature alert threshold.\n"
            "This is a session-only setting (not stored on the UPS).")

        # Temperature history summary
        self._temp_history_var = tk.StringVar(value="No temperature history yet.")
        history_entry = ttk.Entry(frame, textvariable=self._temp_history_var,
                                  state="readonly", font=("Consolas", 8),
                                  width=50)
        history_entry.pack(anchor="w", pady=(5, 0))
        tip(history_entry,
            "Session temperature statistics (min/avg/max)\n"
            "based on readings since connection was established.")

    def _build_cal_panel(self):
        """Build the calibration pre-check panel."""
        frame = ttk.LabelFrame(self, text="Runtime Calibration Pre-Check",
                               padding=8)
        frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        desc_lbl = ttk.Label(
            frame,
            text="Review these values before starting a runtime calibration (D command):",
            foreground="gray40")
        desc_lbl.pack(anchor="w", pady=(0, 5))
        tip(desc_lbl,
            "Runtime calibration discharges the battery to recalculate\n"
            "the remaining runtime estimate. Battery must be at 100%.\n"
            "Smart constants are factory-set discharge curve parameters.")

        # Smart constants display with factory defaults
        const_frame = ttk.Frame(frame)
        const_frame.pack(fill="x", pady=3)

        # Column headers
        ttk.Label(const_frame, text="", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(const_frame, text="Current", anchor="w",
                  font=("TkDefaultFont", 8, "bold")).grid(
            row=0, column=1, sticky="w", padx=(0, 5))
        ttk.Label(const_frame, text="Factory", anchor="w",
                  font=("TkDefaultFont", 8, "bold")).grid(
            row=0, column=2, sticky="w", padx=(5, 5))
        ttk.Label(const_frame, text="", anchor="w").grid(
            row=0, column=3, sticky="w")

        self._cal_const_vars = {}
        self._factory_const_vars = {}
        self._const_match_vars = {}

        const_tips = {
            "cal_sc_0": "Battery constant 0 — controls runtime estimation.\n"
                        "If this differs from factory default, runtime\n"
                        "calibration may produce inaccurate results.",
            "cal_sc_4": "Battery constant 4 — low-end discharge curve parameter.\n"
                        "Factory-set value, normally not modified.",
            "cal_sc_5": "Battery constant 5 — mid-range discharge curve parameter.\n"
                        "Factory-set value, normally not modified.",
            "cal_sc_6": "Battery constant 6 — high-end discharge curve parameter.\n"
                        "Factory-set value, normally not modified.",
        }

        for i, (label, key, reg_key) in enumerate([
            ("Constant 0 (Runtime):", "cal_sc_0", "reg_0"),
            ("Constant 4 (Low):", "cal_sc_4", "reg_4"),
            ("Constant 5 (Mid):", "cal_sc_5", "reg_5"),
            ("Constant 6 (High):", "cal_sc_6", "reg_6"),
        ], start=1):
            lbl = ttk.Label(const_frame, text=label, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=1)
            tip(lbl, const_tips.get(key, ""))

            # Current value
            var = tk.StringVar(value="---")
            self._cal_const_vars[key] = var
            ttk.Entry(const_frame, textvariable=var, state="readonly",
                      font=("Consolas", 10, "bold"), width=8).grid(
                row=i, column=1, sticky="w", pady=1)

            # Factory default value
            fvar = tk.StringVar(value="---")
            self._factory_const_vars[reg_key] = fvar
            ttk.Entry(const_frame, textvariable=fvar, state="readonly",
                      font=("Consolas", 10), width=14).grid(
                row=i, column=2, sticky="w", padx=(5, 5), pady=1)

            # Match indicator
            mvar = tk.StringVar(value="")
            self._const_match_vars[reg_key] = mvar
            ttk.Label(const_frame, textvariable=mvar,
                      font=("TkDefaultFont", 8)).grid(
                row=i, column=3, sticky="w", pady=1)

        # Matched model display
        ref_frame = ttk.Frame(frame)
        ref_frame.pack(fill="x", pady=(5, 0))

        self._matched_model_var = tk.StringVar(value="")
        ttk.Label(ref_frame, textvariable=self._matched_model_var,
                  font=("TkDefaultFont", 8), foreground="gray40").pack(
            side="left")

        # Source attribution link
        link_lbl = ttk.Label(ref_frame, text="[Reference: kirbah/apc-ups]",
                             font=("TkDefaultFont", 8, "underline"),
                             foreground="#0066CC", cursor="hand2")
        link_lbl.pack(side="right")
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open(SOURCE_URL))
        tip(link_lbl,
            "Factory default constants reference data from:\n"
            + SOURCE_URL + "\n"
            "Click to open in browser.")

        # Constant 0 warning
        self._const_warning_var = tk.StringVar(value="")
        self._const_warning_label = ttk.Label(
            frame, textvariable=self._const_warning_var,
            foreground="red", wraplength=500,
            font=("TkDefaultFont", 9, "bold"))
        self._const_warning_label.pack(anchor="w", pady=(5, 0))

        # Calibration readiness section
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(8, 5))

        cal_header = ttk.Frame(frame)
        cal_header.pack(fill="x")
        ttk.Label(cal_header, text="Full Discharge Calibration:",
                  font=("TkDefaultFont", 9, "bold")).pack(side="left")
        ttk.Label(cal_header,
                  text="(NOT the quick 8-second battery test — that is on the Monitor tab)",
                  foreground="red", font=("TkDefaultFont", 8)).pack(side="left", padx=5)

        ready_frame = ttk.Frame(frame)
        ready_frame.pack(fill="x", pady=3)

        # Battery status
        ttk.Label(ready_frame, text="Battery:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=1)
        self._cal_battery_var = tk.StringVar(value="---")
        ttk.Entry(ready_frame, textvariable=self._cal_battery_var,
                  state="readonly", font=("Consolas", 9), width=42).grid(
            row=0, column=1, sticky="w", pady=1)
        tip(ready_frame, "Battery must be at 100% to start runtime calibration.\n"
            "The UPS will refuse the 'D' command otherwise.")

        # Load %
        ttk.Label(ready_frame, text="Load:", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=1)
        self._cal_load_var = tk.StringVar(value="---")
        ttk.Entry(ready_frame, textvariable=self._cal_load_var,
                  state="readonly", font=("Consolas", 9), width=42).grid(
            row=1, column=1, sticky="w", pady=1)

        # Low battery warning
        ttk.Label(ready_frame, text="Low Batt Warning:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=1)
        self._cal_lbw_var = tk.StringVar(value="---")
        ttk.Entry(ready_frame, textvariable=self._cal_lbw_var,
                  state="readonly", font=("Consolas", 9), width=42).grid(
            row=2, column=1, sticky="w", pady=1)

        # Estimated calibration time
        ttk.Label(ready_frame, text="Est. Duration:", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=1)
        self._cal_duration_var = tk.StringVar(value="---")
        ttk.Entry(ready_frame, textvariable=self._cal_duration_var,
                  state="readonly", font=("Consolas", 9), width=42).grid(
            row=3, column=1, sticky="w", pady=1)

        # Calibration action buttons
        cal_btn_frame = ttk.Frame(frame)
        cal_btn_frame.pack(fill="x", pady=(8, 0))

        self._btn_start_cal = ttk.Button(
            cal_btn_frame, text="Start Full Discharge Test",
            command=self._on_start_calibration)
        self._btn_start_cal.pack(side="left", padx=3)
        tip(self._btn_start_cal,
            "Start a FULL battery discharge calibration (D command).\n"
            "This is NOT the quick 8-second self-test!\n\n"
            "The UPS will run on battery until it reaches ~25%,\n"
            "which can take 30 minutes to several hours.\n"
            "All connected equipment runs on battery during this test!")

        self._btn_abort_cal = ttk.Button(
            cal_btn_frame, text="Abort Calibration",
            command=self._on_abort_calibration, state="disabled")
        self._btn_abort_cal.pack(side="left", padx=3)
        tip(self._btn_abort_cal,
            "Abort a running calibration by sending 'D' again.\n"
            "The UPS returns to normal operation and recharges.")

        self._cal_status_var = tk.StringVar(value="")
        self._cal_status_label = ttk.Label(
            cal_btn_frame, textvariable=self._cal_status_var,
            font=("Consolas", 9, "bold"))
        self._cal_status_label.pack(side="left", padx=10)

        # Cache for the last matched model to avoid re-lookup every refresh
        self._last_matched_model = None
        self._factory_defaults = None

    def _build_warning(self):
        """Build the bottom warning label."""
        warn_frame = tk.Frame(self, bg="#FFD700", padx=4, pady=2)
        warn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        warn_lbl = tk.Label(warn_frame,
                            text="Service tools are for experienced technicians. "
                                 "Incorrect changes can damage the UPS or connected equipment.",
                            bg="#FFD700", fg="black",
                            font=("TkDefaultFont", 8, "bold"),
                            wraplength=700)
        warn_lbl.pack()

    # --- PROG mode handlers ---

    def _on_enter_prog(self):
        """Enter PROG mode."""
        result = messagebox.askyesno(
            "Enter PROG Mode",
            "PROG mode allows calibration of voltage readings.\n\n"
            "WARNING: Incorrect calibration can cause:\n"
            "- Overcharging or undercharging batteries\n"
            "- Incorrect transfer behavior\n"
            "- Damage to connected equipment\n\n"
            "Have an external voltmeter ready.\n\n"
            "Enter PROG mode?",
            icon="warning")
        if not result:
            return

        self._btn_prog_enter.config(state="disabled")

        def do_enter():
            success, msg = self.manager.enter_prog_mode()
            self.after(0, lambda: self._prog_enter_done(success, msg))

        threading.Thread(target=do_enter, daemon=True).start()

    def _prog_enter_done(self, success, msg):
        if success:
            self._prog_mode_active = True
            self._btn_prog_plus.config(state="normal")
            self._btn_prog_minus.config(state="normal")
            self._btn_prog_read.config(state="normal")
            self._btn_prog_save.config(state="normal")
            self._btn_prog_exit.config(state="normal")
            self._prog_reading_var.set("PROG mode active")
        else:
            self._btn_prog_enter.config(state="normal")
            messagebox.showerror("PROG Mode", f"Failed to enter PROG mode:\n{msg}")

    def _on_prog_adjust(self, direction):
        """Adjust value in PROG mode."""
        def do_adjust():
            success, response = self.manager.prog_adjust(direction)
            if success:
                self.after(0, lambda: self._prog_reading_var.set(response))
            else:
                self.after(0, lambda: self._prog_reading_var.set(f"Error: {response}"))
        threading.Thread(target=do_adjust, daemon=True).start()

    def _on_prog_read(self):
        """Read current value in PROG mode."""
        cmd = self._prog_cmd_var.get()

        def do_read():
            success, response = self.manager.prog_read(cmd)
            if success:
                self.after(0, lambda: self._prog_reading_var.set(f"{cmd}: {response}"))
            else:
                self.after(0, lambda: self._prog_reading_var.set(f"Error: {response}"))
        threading.Thread(target=do_read, daemon=True).start()

    def _on_prog_save(self):
        """Save value in PROG mode — requires confirmation."""
        result = messagebox.askyesno(
            "Save to EEPROM",
            "This will save the adjusted calibration value to the\n"
            "UPS EEPROM. This change is permanent.\n\n"
            "Are you sure?",
            icon="warning")
        if not result:
            return

        def do_save():
            success, response = self.manager.prog_save()
            self.after(0, lambda: self._prog_reading_var.set(
                f"Saved: {response}" if success else f"Error: {response}"))
        threading.Thread(target=do_save, daemon=True).start()

    def _on_exit_prog(self):
        """Exit PROG mode."""
        def do_exit():
            self.manager.exit_prog_mode()
            self.after(0, self._prog_exit_done)
        threading.Thread(target=do_exit, daemon=True).start()

    def _prog_exit_done(self):
        self._prog_mode_active = False
        self._btn_prog_enter.config(state="normal")
        self._btn_prog_plus.config(state="disabled")
        self._btn_prog_minus.config(state="disabled")
        self._btn_prog_read.config(state="disabled")
        self._btn_prog_save.config(state="disabled")
        self._btn_prog_exit.config(state="disabled")
        self._prog_reading_var.set("---")

    # --- Temperature threshold ---

    def _on_set_threshold(self):
        """Set the temperature alert threshold."""
        try:
            threshold = float(self._temp_threshold_var.get())
            if threshold < 0 or threshold > 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Value",
                                 "Enter a temperature between 0 and 100 C.")
            return
        self.manager.set_temperature_alert_threshold(threshold)

    # --- Runtime calibration handlers ---

    def _on_start_calibration(self):
        """Start runtime calibration after confirmation."""
        from apc_ups.ui.dialogs import DangerousActionDialog
        dialog = DangerousActionDialog(
            self,
            title="Start Full Discharge Calibration",
            description=(
                "This is NOT the quick 8-second battery test!\n\n"
                "This will FULLY DISCHARGE the battery to recalibrate\n"
                "the UPS runtime estimate. The process takes 30 minutes\n"
                "to several hours depending on load and battery capacity.\n\n"
                "During calibration:\n"
                "- ALL connected equipment runs on battery power\n"
                "- The UPS will beep periodically\n"
                "- Battery will discharge to ~25% before stopping\n"
                "- If load exceeds capacity, equipment WILL lose power\n\n"
                "Battery must be at 100% or the UPS will refuse."),
            warning="DANGER: Full battery discharge — equipment runs on battery!",
        )
        if not dialog.result:
            return

        self._btn_start_cal.config(state="disabled")
        self._cal_status_var.set("Starting...")

        def do_start():
            success, msg = self.manager.start_calibration()
            self.after(0, lambda: self._cal_start_done(success, msg))

        threading.Thread(target=do_start, daemon=True).start()

    def _cal_start_done(self, success, msg):
        if success:
            self._btn_abort_cal.config(state="normal")
            self._cal_status_var.set("RUNNING — discharging battery")
        else:
            self._btn_start_cal.config(state="normal")
            self._cal_status_var.set("")
            messagebox.showerror("Calibration Failed",
                                 f"Could not start calibration:\n{msg}")

    def _on_abort_calibration(self):
        """Abort a running calibration."""
        result = messagebox.askyesno(
            "Abort Calibration",
            "Stop the running calibration and return to normal operation?\n\n"
            "The runtime estimate will NOT be updated.",
            icon="warning")
        if not result:
            return

        self._btn_abort_cal.config(state="disabled")

        def do_abort():
            success, msg = self.manager.abort_calibration()
            self.after(0, lambda: self._cal_abort_done(success, msg))

        threading.Thread(target=do_abort, daemon=True).start()

    def _cal_abort_done(self, success, msg):
        self._btn_start_cal.config(state="normal")
        self._btn_abort_cal.config(state="disabled")
        if success:
            self._cal_status_var.set("Aborted")
            self.manager.calibration.reset()
        else:
            self._cal_status_var.set("")
            messagebox.showerror("Abort Failed", f"Could not abort:\n{msg}")

    # --- Display updates ---

    def _update_factory_defaults(self, model_name: str):
        """Look up and cache factory defaults for the connected model."""
        if model_name == self._last_matched_model:
            return  # Already matched
        self._last_matched_model = model_name

        matches = lookup_model(model_name)
        if matches:
            self._factory_defaults = get_factory_defaults(matches[0])
            ref_model = self._factory_defaults["model"]
            batt_v = self._factory_defaults.get("battery_voltage", "")
            info = f"Matched: {ref_model}"
            if batt_v:
                info += f" ({batt_v})"
            if len(matches) > 1:
                others = ", ".join(get_factory_defaults(m)["model"]
                                   for m in matches[1:3])
                info += f"  (also: {others})"
            self._matched_model_var.set(info)
        else:
            self._factory_defaults = None
            self._matched_model_var.set(
                "No factory reference found for this model")

        # Update factory default display fields — show 0x hex prefix
        # and plain decimal to distinguish the two formats clearly
        for reg_key in ("reg_0", "reg_4", "reg_5", "reg_6"):
            if self._factory_defaults:
                dec_val = self._factory_defaults.get(reg_key, "")
                hex_val = self._factory_defaults.get(f"{reg_key}_hex", "")
                if hex_val:
                    dec_int = int(dec_val) if dec_val else 0
                    self._factory_const_vars[reg_key].set(
                        f"0x{hex_val} ({dec_int})")
                else:
                    self._factory_const_vars[reg_key].set("n/a")
            else:
                self._factory_const_vars[reg_key].set("---")

    def update_display(self, state_dict: dict):
        """Update service tab displays from UPS state snapshot."""
        # Temperature display
        temp = state_dict.get("temperature", 0)
        if temp > 0:
            self._temp_display_var.set(f"Current: {temp:.1f} C")
        else:
            self._temp_display_var.set("Current: ---")

        # Temperature history summary
        history = state_dict.get("temperature_history", [])
        if history:
            temps = [t for _, t in history]
            avg = sum(temps) / len(temps)
            mn, mx = min(temps), max(temps)
            self._temp_history_var.set(
                f"Session: {len(temps)} readings | "
                f"Avg: {avg:.1f} C | Min: {mn:.1f} C | Max: {mx:.1f} C")

        # Calibration pre-check: smart constants
        for suffix in ("0", "4", "5", "6"):
            val = state_dict.get(f"smart_constant_{suffix}", "")
            self._cal_const_vars[f"cal_sc_{suffix}"].set(val if val else "---")

        # Look up factory defaults based on model name
        model_name = state_dict.get("model", "")
        if model_name:
            self._update_factory_defaults(model_name)

        # Compare current vs factory defaults
        # The UPS may return constants as hex strings (e.g. "81", "BC")
        # or as 3-digit decimal strings (e.g. "129", "188") depending on
        # firmware. Compare against both the hex and decimal forms.
        reg_map = {"reg_0": "0", "reg_4": "4", "reg_5": "5", "reg_6": "6"}
        for reg_key, suffix in reg_map.items():
            current = state_dict.get(f"smart_constant_{suffix}", "")
            if not current or not self._factory_defaults:
                self._const_match_vars[reg_key].set("")
                continue
            factory_dec = self._factory_defaults.get(reg_key, "")
            factory_hex = self._factory_defaults.get(f"{reg_key}_hex", "")
            cur = current.strip().upper()
            if not factory_dec and not factory_hex:
                self._const_match_vars[reg_key].set("")
            elif (cur == factory_dec.strip()
                  or cur == factory_hex.strip().upper()
                  or cur.lstrip("0") == factory_hex.strip().upper().lstrip("0")):
                self._const_match_vars[reg_key].set("OK")
            else:
                self._const_match_vars[reg_key].set("MODIFIED")

        # Constant 0 warning from calibration manager
        warning = self.manager.calibration.constant_0_warning
        self._const_warning_var.set(warning)

        # Calibration readiness checks
        batt = state_dict.get("battery_capacity", 0)
        if batt >= 100.0:
            self._cal_battery_var.set(f"{batt:.1f}% -- READY")
        elif batt > 0:
            self._cal_battery_var.set(f"{batt:.1f}% -- Must be 100%")
        else:
            self._cal_battery_var.set("---")

        # Load % with recommendation
        load = state_dict.get("load_power", 0)
        if load > 0:
            if load >= 25:
                self._cal_load_var.set(f"{load:.0f}% -- OK for calibration")
            else:
                self._cal_load_var.set(
                    f"{load:.0f}% -- Low! Recommend >= 25% for accuracy")
        else:
            self._cal_load_var.set("---")

        # Low battery warning time (determines when calibration stops)
        lbw = state_dict.get("low_battery_warning", "")
        if lbw:
            self._cal_lbw_var.set(
                f"{lbw} min -- calibration stops at this runtime")
        else:
            self._cal_lbw_var.set("---")

        # Estimated calibration duration
        runtime = state_dict.get("runtime_remaining", 0)
        if runtime > 0 and lbw:
            try:
                lbw_min = float(lbw.strip())
                est_duration = runtime - lbw_min
                if est_duration > 0:
                    if est_duration >= 60:
                        hrs = int(est_duration // 60)
                        mins = int(est_duration % 60)
                        self._cal_duration_var.set(
                            f"~{hrs}h {mins}m (runtime {runtime:.0f}m - "
                            f"LBW {lbw_min:.0f}m)")
                    else:
                        self._cal_duration_var.set(
                            f"~{est_duration:.0f} min (runtime {runtime:.0f}m"
                            f" - LBW {lbw_min:.0f}m)")
                else:
                    self._cal_duration_var.set("Runtime too low to calibrate")
            except ValueError:
                self._cal_duration_var.set("---")
        else:
            self._cal_duration_var.set("---")

        # Live calibration status
        from apc_ups.core.calibration import CalibrationState
        cal_state = self.manager.calibration.state
        if cal_state == CalibrationState.RUNNING:
            self.manager.calibration.update_progress(batt)
            progress = self.manager.calibration.progress_pct
            self._cal_status_var.set(
                f"RUNNING — battery {batt:.0f}% ({progress:.0f}% done)")
            self._btn_start_cal.config(state="disabled")
            self._btn_abort_cal.config(state="normal")
        elif cal_state == CalibrationState.COMPLETED:
            self._cal_status_var.set("COMPLETED — runtime recalibrated")
            self._btn_start_cal.config(state="normal")
            self._btn_abort_cal.config(state="disabled")
            self.manager.calibration.reset()
        elif cal_state in (CalibrationState.IDLE, CalibrationState.FAILED,
                           CalibrationState.ABORTED):
            if not self.manager.calibration.is_active:
                self._btn_abort_cal.config(state="disabled")

    def set_buttons_enabled(self, enabled: bool):
        """Enable or disable service buttons."""
        state = "normal" if enabled else "disabled"
        if not self._prog_mode_active:
            self._btn_prog_enter.config(state=state)
        self._btn_set_threshold.config(state=state)
        if not self.manager.calibration.is_active:
            self._btn_start_cal.config(state=state)
