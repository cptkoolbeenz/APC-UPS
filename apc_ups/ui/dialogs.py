"""Confirmation dialogs — normal, caution, and dangerous tiers."""

import tkinter as tk
from tkinter import ttk

from apc_ups.core.editable_settings import DangerLevel


class SettingChangeDialog(tk.Toplevel):
    """Dialog for changing an editable UPS setting.

    Three tiers:
    - NORMAL (green):  Simple confirmation
    - CAUTION (yellow): Shows explanation, Cancel focused by default
    - DANGEROUS (red):  Red banner, user must type 'YES' to enable Apply
    """

    def __init__(self, parent, setting_name: str, current_value: str,
                 allowed_values: list[str], labels: dict[str, str],
                 danger: DangerLevel, description: str = "",
                 direct_edit: bool = False, unit: str = "",
                 discovered_values: list[str] | None = None):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        self.result = None  # Will hold the selected value on Apply

        self.title(f"Change: {setting_name}")
        self.resizable(False, False)

        self._danger = danger
        self._direct_edit = direct_edit

        # Use discovered values when available, fall back to hardcoded.
        # When using discovered values, clear spec labels so all values
        # display consistently (the spec labels only match old firmware).
        if discovered_values is not None:
            allowed_values = discovered_values
            labels = {}

        # Configure dialog appearance based on danger level
        if danger == DangerLevel.DANGEROUS:
            self._build_dangerous(setting_name, current_value, description)
        elif danger == DangerLevel.CAUTION:
            self._build_caution(setting_name, current_value, allowed_values,
                                labels, description, unit, direct_edit)
        else:
            self._build_normal(setting_name, current_value, allowed_values,
                               labels, description, unit, direct_edit)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_window()

    def _build_normal(self, name, current, values, labels, desc, unit, direct_edit):
        """Build a normal (green) confirmation dialog."""
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"Change: {name}",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        if desc:
            ttk.Label(frame, text=desc, wraplength=350,
                      foreground="gray40").pack(anchor="w", pady=(2, 8))

        current_disp = labels.get(current, current)
        ttk.Label(frame, text=f"Current value: {current_disp}",
                  font=("Consolas", 10)).pack(anchor="w", pady=(0, 8))

        if direct_edit:
            self._build_text_input(frame, current, unit)
        else:
            self._build_radio_select(frame, values, labels, current, unit)

        self._build_buttons(frame, focus_cancel=False)

    def _build_caution(self, name, current, values, labels, desc, unit,
                       direct_edit=False):
        """Build a caution (yellow) dialog."""
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        # Yellow warning banner
        warn_frame = tk.Frame(frame, bg="#FFD700", padx=8, pady=4)
        warn_frame.pack(fill="x", pady=(0, 10))
        tk.Label(warn_frame, text="CAUTION: This changes UPS behavior",
                 bg="#FFD700", fg="black",
                 font=("TkDefaultFont", 10, "bold")).pack()

        ttk.Label(frame, text=f"Change: {name}",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        if desc:
            ttk.Label(frame, text=desc, wraplength=350,
                      foreground="gray40").pack(anchor="w", pady=(2, 8))

        current_disp = labels.get(current, current)
        ttk.Label(frame, text=f"Current value: {current_disp}",
                  font=("Consolas", 10, "bold")).pack(anchor="w", pady=(0, 8))

        if direct_edit:
            self._build_text_input(frame, current, unit)
        else:
            self._build_radio_select(frame, values, labels, current, unit)
        self._build_buttons(frame, focus_cancel=True)

    def _build_dangerous(self, name, current, desc):
        """Build a dangerous (red) dialog requiring 'YES' input."""
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        # Red warning banner
        warn_frame = tk.Frame(frame, bg="#FF3333", padx=8, pady=8)
        warn_frame.pack(fill="x", pady=(0, 10))
        tk.Label(warn_frame, text="DANGER: This operation cannot be easily undone!",
                 bg="#FF3333", fg="white",
                 font=("TkDefaultFont", 11, "bold")).pack()

        ttk.Label(frame, text=name,
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        if desc:
            ttk.Label(frame, text=desc, wraplength=350,
                      foreground="red").pack(anchor="w", pady=(2, 10))

        ttk.Label(frame, text='Type "YES" to confirm:',
                  font=("TkDefaultFont", 10)).pack(anchor="w", pady=(5, 2))

        self._confirm_var = tk.StringVar()
        self._confirm_var.trace_add("write", self._on_confirm_text_changed)
        self._confirm_entry = ttk.Entry(frame, textvariable=self._confirm_var, width=10)
        self._confirm_entry.pack(anchor="w", pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        self._btn_apply = ttk.Button(btn_frame, text="Execute",
                                     command=self._on_apply, state="disabled")
        self._btn_apply.pack(side="right", padx=5)

        self._btn_cancel = ttk.Button(btn_frame, text="Cancel",
                                      command=self._on_cancel)
        self._btn_cancel.pack(side="right", padx=5)
        self._btn_cancel.focus_set()

    def _build_radio_select(self, parent, values, labels, current, unit):
        """Build radio button selection for allowed values."""
        self._selected = tk.StringVar(value=current)

        # If current value is not in the value list, prepend it
        if current and current not in values:
            values = [current] + list(values)

        # Deduplicate values for display
        seen = set()
        unique_values = []
        for v in values:
            if v not in seen:
                seen.add(v)
                unique_values.append(v)

        # Sort numerically when all values are numeric, otherwise keep order
        try:
            unique_values.sort(key=lambda v: float(v))
        except ValueError:
            pass  # Non-numeric values (H/M/L, ON/OFF) — keep discovery order

        for val in unique_values:
            display = labels.get(val, val)
            if unit and val not in labels:
                display = f"{val} {unit}"
            ttk.Radiobutton(parent, text=display, variable=self._selected,
                            value=val).pack(anchor="w", padx=10, pady=1)

    def _build_text_input(self, parent, current, unit):
        """Build text input for direct edit settings (UPS ID, battery date)."""
        self._selected = tk.StringVar(value=current)
        input_frame = ttk.Frame(parent)
        input_frame.pack(anchor="w", pady=5)
        ttk.Label(input_frame, text="New value:").pack(side="left")
        entry = ttk.Entry(input_frame, textvariable=self._selected, width=12)
        entry.pack(side="left", padx=5)
        entry.select_range(0, "end")
        entry.focus_set()
        if unit:
            ttk.Label(input_frame, text=unit).pack(side="left")

    def _build_buttons(self, parent, focus_cancel: bool):
        """Build Cancel and Apply buttons."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=(15, 0))

        self._btn_apply = ttk.Button(btn_frame, text="Apply",
                                     command=self._on_apply)
        self._btn_apply.pack(side="right", padx=5)

        self._btn_cancel = ttk.Button(btn_frame, text="Cancel",
                                      command=self._on_cancel)
        self._btn_cancel.pack(side="right", padx=5)

        if focus_cancel:
            self._btn_cancel.focus_set()
        else:
            self._btn_apply.focus_set()

    def _on_confirm_text_changed(self, *args):
        """Enable Execute button only when user types exactly 'YES'."""
        if self._confirm_var.get() == "YES":
            self._btn_apply.config(state="normal")
        else:
            self._btn_apply.config(state="disabled")

    def _on_apply(self):
        if self._danger == DangerLevel.DANGEROUS:
            self.result = "YES"
        else:
            self.result = self._selected.get()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class DangerousActionDialog(tk.Toplevel):
    """Dialog for dangerous power commands (shutdown, calibration, reset).

    Requires user to type 'YES' to confirm.
    """

    def __init__(self, parent, title: str, description: str,
                 warning: str = ""):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        self.result = False
        self.title(title)
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        # Red warning banner
        warn_frame = tk.Frame(frame, bg="#FF3333", padx=8, pady=8)
        warn_frame.pack(fill="x", pady=(0, 10))
        tk.Label(warn_frame,
                 text=warning or "DANGER: This operation may affect connected equipment!",
                 bg="#FF3333", fg="white",
                 font=("TkDefaultFont", 11, "bold"),
                 wraplength=350).pack()

        ttk.Label(frame, text=description, wraplength=380,
                  font=("TkDefaultFont", 10)).pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text='Type "YES" to confirm:',
                  font=("TkDefaultFont", 10)).pack(anchor="w", pady=(5, 2))

        self._confirm_var = tk.StringVar()
        self._confirm_var.trace_add("write", self._on_text_changed)
        entry = ttk.Entry(frame, textvariable=self._confirm_var, width=10)
        entry.pack(anchor="w", pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        self._btn_execute = ttk.Button(btn_frame, text="Execute",
                                       command=self._on_execute, state="disabled")
        self._btn_execute.pack(side="right", padx=5)

        btn_cancel = ttk.Button(btn_frame, text="Cancel",
                                command=self._on_cancel)
        btn_cancel.pack(side="right", padx=5)
        btn_cancel.focus_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_window()

    def _on_text_changed(self, *args):
        if self._confirm_var.get() == "YES":
            self._btn_execute.config(state="normal")
        else:
            self._btn_execute.config(state="disabled")

    def _on_execute(self):
        self.result = True
        self.destroy()

    def _on_cancel(self):
        self.result = False
        self.destroy()
