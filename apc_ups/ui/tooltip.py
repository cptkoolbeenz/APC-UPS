"""Hover tooltips for tkinter widgets."""

import tkinter as tk


class ToolTip:
    """Shows a tooltip popup when the mouse hovers over a widget.

    Usage:
        button = ttk.Button(parent, text="Save")
        ToolTip(button, "Save the current value to EEPROM")
    """

    DELAY = 400  # ms before tooltip appears

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.DELAY, self._show)

    def _cancel(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffe0", foreground="#333333",
            relief="solid", borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=6, pady=4, wraplength=380,
        )
        label.pack()

    def _hide(self):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def tip(widget, text: str) -> ToolTip:
    """Shorthand to attach a tooltip to a widget."""
    return ToolTip(widget, text)
