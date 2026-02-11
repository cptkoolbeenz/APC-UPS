"""Graph tab — battery voltage and charge percentage over time."""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from apc_ups.ui.tooltip import tip


# Chart layout constants
MARGIN_LEFT = 60
MARGIN_RIGHT = 60
MARGIN_TOP = 20
MARGIN_BOTTOM = 40


class GraphTab(ttk.Frame):
    """Displays a real-time graph of battery voltage and charge percent."""

    # Time window options: (label, timedelta)
    TIME_WINDOWS = [
        ("5 Min", timedelta(minutes=5)),
        ("15 Min", timedelta(minutes=15)),
        ("30 Min", timedelta(minutes=30)),
        ("1 Hour", timedelta(hours=1)),
    ]

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self._time_window = self.TIME_WINDOWS[1][1]  # Default 15 min
        self._build_ui()

    def _build_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Canvas for drawing
        self._canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=(5, 0))

        # Control bar below chart
        ctrl = ttk.Frame(self, padding=4)
        ctrl.grid(row=1, column=0, sticky="ew", padx=5, pady=2)

        ttk.Label(ctrl, text="Time window:").pack(side="left", padx=(0, 5))

        self._window_var = tk.StringVar(value=self.TIME_WINDOWS[1][0])
        for label, td in self.TIME_WINDOWS:
            btn = ttk.Radiobutton(ctrl, text=label, variable=self._window_var,
                                  value=label, command=self._on_window_change)
            btn.pack(side="left", padx=3)

        # Legend
        legend = ttk.Frame(ctrl)
        legend.pack(side="right", padx=10)

        cv = tk.Canvas(legend, width=14, height=14, highlightthickness=0)
        cv.create_rectangle(2, 2, 12, 12, fill="#2196F3", outline="#1565C0")
        cv.pack(side="left")
        ttk.Label(legend, text="Voltage (V)").pack(side="left", padx=(2, 10))

        cv2 = tk.Canvas(legend, width=14, height=14, highlightthickness=0)
        cv2.create_rectangle(2, 2, 12, 12, fill="#4CAF50", outline="#2E7D32")
        cv2.pack(side="left")
        ttk.Label(legend, text="Charge (%)").pack(side="left", padx=(2, 0))

        # Bind resize
        self._canvas.bind("<Configure>", lambda e: self._draw())

    def _on_window_change(self):
        label = self._window_var.get()
        for name, td in self.TIME_WINDOWS:
            if name == label:
                self._time_window = td
                break
        self._draw()

    def update_display(self, state_dict: dict):
        """Called by app.py on each UI refresh cycle."""
        self._draw()

    def _draw(self):
        """Redraw the entire chart."""
        canvas = self._canvas
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 100 or h < 80:
            return

        canvas.delete("all")

        # Chart area
        x0 = MARGIN_LEFT
        y0 = MARGIN_TOP
        x1 = w - MARGIN_RIGHT
        y1 = h - MARGIN_BOTTOM
        cw = x1 - x0
        ch = y1 - y0

        if cw < 20 or ch < 20:
            return

        # Get history data within the time window
        history = self.manager.state.battery_history
        now = datetime.now()
        t_start = now - self._time_window

        # Filter data within window
        data = [(t, v, c) for t, v, c in history if t >= t_start]

        # Draw background and grid
        canvas.create_rectangle(x0, y0, x1, y1, fill="#FAFAFA", outline="#CCCCCC")

        # Voltage Y-axis (left): auto-range based on data
        if data:
            voltages = [v for _, v, _ in data if v > 0]
            if voltages:
                v_min = min(voltages)
                v_max = max(voltages)
                # Add 5% padding
                v_range = v_max - v_min
                if v_range < 1.0:
                    v_range = 2.0
                    v_min = v_min - 1.0
                v_min = v_min - v_range * 0.1
                v_max = v_max + v_range * 0.1
            else:
                v_min, v_max = 40.0, 60.0
        else:
            v_min, v_max = 40.0, 60.0

        # Charge Y-axis (right): always 0-100%
        c_min, c_max = 0.0, 100.0

        # Draw horizontal grid lines (5 divisions)
        n_grid = 5
        for i in range(n_grid + 1):
            frac = i / n_grid
            y = y1 - frac * ch

            # Grid line
            canvas.create_line(x0, y, x1, y, fill="#E0E0E0", dash=(2, 4))

            # Voltage label (left axis)
            v_val = v_min + frac * (v_max - v_min)
            canvas.create_text(x0 - 5, y, text=f"{v_val:.1f}",
                               anchor="e", font=("Consolas", 8),
                               fill="#1565C0")

            # Charge label (right axis)
            c_val = c_min + frac * (c_max - c_min)
            canvas.create_text(x1 + 5, y, text=f"{c_val:.0f}%",
                               anchor="w", font=("Consolas", 8),
                               fill="#2E7D32")

        # Y-axis titles
        canvas.create_text(12, (y0 + y1) / 2, text="Volts",
                           angle=90, anchor="center",
                           font=("TkDefaultFont", 9, "bold"), fill="#1565C0")
        canvas.create_text(w - 8, (y0 + y1) / 2, text="Charge %",
                           angle=90, anchor="center",
                           font=("TkDefaultFont", 9, "bold"), fill="#2E7D32")

        # Draw time axis labels
        t_total = self._time_window.total_seconds()
        n_time_labels = min(6, max(3, cw // 80))
        for i in range(n_time_labels + 1):
            frac = i / n_time_labels
            x = x0 + frac * cw
            t = t_start + timedelta(seconds=frac * t_total)

            canvas.create_line(x, y1, x, y1 + 4, fill="#999999")
            canvas.create_text(x, y1 + 6, text=t.strftime("%H:%M:%S"),
                               anchor="n", font=("Consolas", 7),
                               fill="#666666")

        if not data:
            canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                               text="No data yet — connect to UPS",
                               font=("TkDefaultFont", 11), fill="#999999")
            return

        # Plot voltage line (blue)
        voltage_points = []
        for t, v, c in data:
            if v <= 0:
                continue
            elapsed = (t - t_start).total_seconds()
            frac_x = elapsed / t_total
            frac_y = (v - v_min) / (v_max - v_min)
            px = x0 + frac_x * cw
            py = y1 - frac_y * ch
            voltage_points.append((px, py))

        if len(voltage_points) >= 2:
            flat = [coord for pt in voltage_points for coord in pt]
            canvas.create_line(*flat, fill="#2196F3", width=2, smooth=True)

        # Plot charge line (green)
        charge_points = []
        for t, v, c in data:
            if c <= 0:
                continue
            elapsed = (t - t_start).total_seconds()
            frac_x = elapsed / t_total
            frac_y = (c - c_min) / (c_max - c_min)
            px = x0 + frac_x * cw
            py = y1 - frac_y * ch
            charge_points.append((px, py))

        if len(charge_points) >= 2:
            flat = [coord for pt in charge_points for coord in pt]
            canvas.create_line(*flat, fill="#4CAF50", width=2, smooth=True)

        # Current value indicators (rightmost point)
        if voltage_points:
            lx, ly = voltage_points[-1]
            canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4,
                               fill="#2196F3", outline="#1565C0")
            last_v = data[-1][1]
            canvas.create_text(lx - 8, ly - 10,
                               text=f"{last_v:.2f}V",
                               anchor="e", font=("Consolas", 8, "bold"),
                               fill="#1565C0")

        if charge_points:
            lx, ly = charge_points[-1]
            canvas.create_oval(lx - 4, ly - 4, lx + 4, ly + 4,
                               fill="#4CAF50", outline="#2E7D32")
            last_c = data[-1][2]
            canvas.create_text(lx + 8, ly - 10,
                               text=f"{last_c:.1f}%",
                               anchor="w", font=("Consolas", 8, "bold"),
                               fill="#2E7D32")

    def set_buttons_enabled(self, enabled: bool):
        """No buttons to enable/disable on this tab."""
        pass
