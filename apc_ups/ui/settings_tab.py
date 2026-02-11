"""Settings tab — editable settings with Change buttons and three-tier confirmation."""

import tkinter as tk
from tkinter import ttk
import threading

from apc_ups.core.editable_settings import SETTINGS, DangerLevel
from apc_ups.ui.dialogs import SettingChangeDialog, DangerousActionDialog
from apc_ups.ui.tooltip import tip


# Display order for settings
SETTINGS_ORDER = [
    "low_battery_warning",
    "shutdown_delay",
    "turn_on_delay",
    "self_test_interval",
    "min_battery_restart",
    "sensitivity",
    "alarm_control",
    "upper_transfer_voltage",
    "lower_transfer_voltage",
    "output_voltage_setting",
    "battery_packs",
    "ups_id",
    "battery_replace_date",
]

# Tooltips for the left-panel UPS info fields
_INFO_TIPS = {
    "model": "UPS model name reported by the unit.",
    "firmware": "Internal firmware version (determines feature set).",
    "manufacture_date": "Date the UPS was manufactured (from EEPROM).",
    "battery_replace_date": "Date batteries were last replaced.\nUpdate this after every battery swap.",
    "ups_id": "8-character user-assigned identifier stored in EEPROM.",
    "serial_number": "Factory serial number (read-only, cannot be changed).",
    "frequency": "Measured AC line frequency in Hertz.",
    "temperature": "Internal UPS temperature in degrees Celsius.\nHigh temperatures reduce battery life.",
    "nominal_battery_voltage": "Nominal DC battery bus voltage.\nDetermined by UPS model and configuration.",
}


class SettingsTab(ttk.Frame):
    """The Settings tab — shows editable UPS settings with Change buttons."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self._change_in_progress = False
        self._value_vars: dict[str, tk.StringVar] = {}
        self._change_buttons: dict[str, ttk.Button] = {}

        self._build_ui()

    def _build_ui(self):
        # Left panel — UPS identity info
        left_frame = ttk.LabelFrame(self, text="UPS Identity", padding=8)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._info_vars = {}
        info_fields = [
            ("Model:", "model"),
            ("Firmware:", "firmware"),
            ("Manufactured:", "manufacture_date"),
            ("Batteries Replaced:", "battery_replace_date"),
            ("UPS ID:", "ups_id"),
            ("Serial Number:", "serial_number"),
            ("Line Frequency:", "frequency"),
            ("Internal Temp:", "temperature"),
            ("Battery System:", "nominal_battery_voltage"),
        ]

        for i, (label_text, key) in enumerate(info_fields):
            lbl = ttk.Label(left_frame, text=label_text, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            tip(lbl, _INFO_TIPS.get(key, ""))

            var = tk.StringVar(value="---")
            self._info_vars[key] = var
            val_entry = ttk.Entry(left_frame, textvariable=var, state="readonly",
                                  width=18, font=("Consolas", 10, "bold"),
                                  justify="right")
            val_entry.grid(row=i, column=1, sticky="e", padx=(10, 0), pady=2)

        # Warning label
        self._warning_label = ttk.Label(
            left_frame,
            text="USE CAUTION.\n"
                 "Incorrect settings can affect UPS\n"
                 "protection and battery life.",
            foreground="red", font=("TkDefaultFont", 9, "bold"),
            justify="center",
        )
        self._warning_label.grid(row=len(info_fields), column=0, columnspan=2,
                                 sticky="ew", pady=(10, 0))
        tip(self._warning_label,
            "All setting changes are written to the UPS EEPROM.\n"
            "Changes take effect immediately and persist across power cycles.")

        # Right panel — editable settings
        right_frame = ttk.Frame(self, padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 5), pady=5)

        for i, key in enumerate(SETTINGS_ORDER):
            setting = SETTINGS[key]

            name_lbl = ttk.Label(right_frame, text=setting.name, anchor="w")
            name_lbl.grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            tip(name_lbl, setting.description)

            var = tk.StringVar(value="---")
            self._value_vars[key] = var
            val_entry = ttk.Entry(right_frame, textvariable=var, state="readonly",
                                  width=8, font=("Consolas", 10, "bold"),
                                  justify="right")
            val_entry.grid(row=i, column=1, sticky="e", padx=5, pady=3)

            if setting.unit:
                ttk.Label(right_frame, text=setting.unit).grid(
                    row=i, column=2, sticky="w", padx=(0, 5), pady=3)
            else:
                ttk.Label(right_frame, text="").grid(
                    row=i, column=2, sticky="w", padx=(0, 5), pady=3)

            btn = ttk.Button(right_frame, text="Change", width=8,
                             command=lambda k=key: self._on_change(k))
            btn.grid(row=i, column=3, padx=5, pady=3)
            self._change_buttons[key] = btn

            # Tooltip on Change button — danger-level specific
            if setting.danger == DangerLevel.CAUTION:
                tip(btn, f"Change {setting.name}.\n"
                         f"{setting.description}\n"
                         f"Caution: affects UPS behavior.")
            else:
                tip(btn, f"Change {setting.name}.\n{setting.description}")

        # Refresh Settings button
        row = len(SETTINGS_ORDER)
        self._btn_refresh = ttk.Button(right_frame, text="Refresh Settings",
                                       command=self._on_refresh)
        self._btn_refresh.grid(row=row, column=0, columnspan=2, pady=(15, 5),
                               sticky="e")
        tip(self._btn_refresh,
            "Re-read all editable settings from the UPS EEPROM.\n"
            "Use after manual changes or to verify current values.")

        # Factory Reset button
        self._btn_reset = ttk.Button(right_frame, text="Factory Reset Settings",
                                     command=self._on_reset_all)
        self._btn_reset.grid(row=row, column=2, columnspan=2, pady=(15, 5),
                             sticky="w")
        tip(self._btn_reset,
            "Reset ALL UPS settings to factory defaults.\n"
            "Transfer voltages, sensitivity, delays, alarms, and\n"
            "self-test interval will be reverted.\n"
            "UPS ID and Battery Date are NOT affected.\n"
            "Requires typing YES to confirm.")

    def _on_change(self, setting_key: str):
        """Handle Change button click for a setting."""
        if self._change_in_progress:
            return

        setting = SETTINGS[setting_key]
        current = self._value_vars[setting_key].get().strip()

        # Use discovered values when available
        discovered = self.manager.get_discovered_values(setting_key)

        if setting.direct_edit:
            # Direct text input for UPS ID and battery date
            dialog = SettingChangeDialog(
                self, setting.name, current,
                setting.allowed_values, setting.labels,
                setting.danger, setting.description,
                direct_edit=True, unit=setting.unit,
            )
        else:
            dialog = SettingChangeDialog(
                self, setting.name, current,
                setting.allowed_values, setting.labels,
                setting.danger, setting.description,
                unit=setting.unit,
                discovered_values=discovered,
            )

        if dialog.result is not None and dialog.result != current:
            self._execute_change(setting_key, dialog.result)

    def _execute_change(self, setting_key: str, target_value: str):
        """Execute a setting change in a background thread."""
        self._change_in_progress = True
        self._set_all_buttons_state("disabled")

        def do_change():
            success, message = self.manager.change_setting(setting_key, target_value)
            self.after(0, lambda: self._change_done(setting_key, success, message))

        threading.Thread(target=do_change, daemon=True).start()

    def _change_done(self, setting_key: str, success: bool, message: str):
        """Handle change result on the main thread."""
        self._change_in_progress = False
        self._set_all_buttons_state("normal")

        if not success:
            from tkinter import messagebox
            messagebox.showerror("Setting Change Failed",
                                 f"Could not change setting:\n{message}")

    def _on_refresh(self):
        """Re-read all settings from UPS EEPROM."""
        if self._change_in_progress:
            return
        self._change_in_progress = True
        self._set_all_buttons_state("disabled")

        def do_refresh():
            self.manager.refresh_settings()
            self.after(0, lambda: self._change_done("", True, ""))

        threading.Thread(target=do_refresh, daemon=True).start()

    def _on_reset_all(self):
        """Reset all EEPROM settings to factory defaults."""
        dialog = DangerousActionDialog(
            self,
            title="Factory Reset Settings",
            description="This will reset ALL UPS settings to factory defaults.\n"
                        "This includes transfer voltages, sensitivity, delays, "
                        "alarm settings, and self-test interval.\n\n"
                        "UPS ID and Battery Replacement Date will NOT be affected.",
            warning="DANGER: All settings will be reset to factory defaults!",
        )
        if dialog.result:
            self._change_in_progress = True
            self._set_all_buttons_state("disabled")

            def do_reset():
                success, msg = self.manager.reset_eeprom()
                self.after(0, lambda: self._change_done("", success, msg))

            threading.Thread(target=do_reset, daemon=True).start()

    def _set_all_buttons_state(self, state: str):
        """Enable or disable all change buttons."""
        for btn in self._change_buttons.values():
            btn.config(state=state)
        self._btn_refresh.config(state=state)
        self._btn_reset.config(state=state)

    def update_display(self, state_dict: dict):
        """Update setting values from UPS state snapshot."""
        # Update left panel info
        for key, var in self._info_vars.items():
            val = state_dict.get(key, "---")
            if key == "frequency" and val and val != "---":
                try:
                    var.set(f"{float(val):.2f}  Hz")
                except (ValueError, TypeError):
                    var.set(str(val))
            elif key == "temperature" and val and val != "---":
                try:
                    var.set(f"{float(val):.1f}  C")
                except (ValueError, TypeError):
                    var.set(str(val))
            elif key == "nominal_battery_voltage" and val and val != "---":
                var.set(f"{val}  V")
            else:
                var.set(str(val) if val else "---")

        # Update setting values
        for key in SETTINGS_ORDER:
            setting = SETTINGS[key]
            val = state_dict.get(setting.state_key, "---")
            if val:
                self._value_vars[key].set(str(val))

    def set_buttons_enabled(self, enabled: bool):
        """Enable or disable all buttons."""
        state = "normal" if enabled else "disabled"
        self._set_all_buttons_state(state)
