"""Main tkinter application window — port selector, tab management, status bar."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging

from apc_ups.core.ups_manager import UPSManager
from apc_ups.util.port_scanner import scan_ports
from apc_ups.ui.main_tab import MainTab
from apc_ups.ui.tooltip import tip

logger = logging.getLogger(__name__)

# Lazy imports for tabs that are created on demand
_SettingsTab = None
_StatusTab = None
_ServiceTab = None
_GraphTab = None


def _get_settings_tab():
    global _SettingsTab
    if _SettingsTab is None:
        from apc_ups.ui.settings_tab import SettingsTab
        _SettingsTab = SettingsTab
    return _SettingsTab


def _get_status_tab():
    global _StatusTab
    if _StatusTab is None:
        from apc_ups.ui.status_tab import StatusTab
        _StatusTab = StatusTab
    return _StatusTab


def _get_service_tab():
    global _ServiceTab
    if _ServiceTab is None:
        from apc_ups.ui.service_tab import ServiceTab
        _ServiceTab = ServiceTab
    return _ServiceTab


def _get_graph_tab():
    global _GraphTab
    if _GraphTab is None:
        from apc_ups.ui.graph_tab import GraphTab
        _GraphTab = GraphTab
    return _GraphTab


class APCUPSApp:
    """Main application window."""

    REFRESH_INTERVAL = 1000  # ms between UI refreshes

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("APC UPS Manager")
        self.root.geometry("780x680")
        self.root.minsize(700, 580)

        self.manager = UPSManager()
        self.manager.set_message_callback(self._on_message)
        self.manager.set_alert_callback(self._on_alert)

        self._closing = False
        self._refresh_after_id = None

        self._build_ui()
        self._schedule_refresh()

    def _build_ui(self):
        """Build the main application UI."""
        # --- Top bar: port selector and connection buttons ---
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill="x")

        lbl = ttk.Label(top_frame, text="Serial Port:")
        lbl.pack(side="left", padx=(0, 5))
        tip(lbl, "Select the COM port connected to the UPS serial cable.")

        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(top_frame, textvariable=self._port_var,
                                        width=15, state="readonly")
        self._port_combo.pack(side="left", padx=2)
        tip(self._port_combo,
            "Available serial ports detected on this computer.")

        btn_scan = ttk.Button(top_frame, text="Scan Ports",
                              command=self._refresh_ports)
        btn_scan.pack(side="left", padx=2)
        tip(btn_scan, "Re-scan for available serial/COM ports.\n"
                      "Use after plugging in a USB-serial adapter.")

        self._btn_connect = ttk.Button(top_frame, text="Connect",
                                       command=self._on_connect)
        self._btn_connect.pack(side="left", padx=5)
        tip(self._btn_connect,
            "Connect to the UPS on the selected port.\n"
            "Enters Smart Mode and reads all UPS values.")

        self._btn_disconnect = ttk.Button(top_frame, text="Disconnect",
                                          command=self._on_disconnect,
                                          state="disabled")
        self._btn_disconnect.pack(side="left", padx=2)
        tip(self._btn_disconnect,
            "Stop monitoring and close the serial connection.")

        self._polling_paused = False
        self._btn_pause = ttk.Button(top_frame, text="Pause Polling",
                                     command=self._on_toggle_polling,
                                     state="disabled")
        self._btn_pause.pack(side="left", padx=10)
        tip(self._btn_pause,
            "Pause/resume periodic UPS polling.\n"
            "Pausing stops TX/RX traffic so you can observe\n"
            "individual setting changes in the Event Log.")

        # --- Tab notebook ---
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=(0, 0))

        # Smart-UPS tab
        self._main_tab = MainTab(self._notebook, self.manager)
        self._notebook.add(self._main_tab, text="Monitor")

        # Settings tab
        SettingsTab = _get_settings_tab()
        self._settings_tab = SettingsTab(self._notebook, self.manager)
        self._notebook.add(self._settings_tab, text="Settings")

        # Status tab
        StatusTab = _get_status_tab()
        self._status_tab = StatusTab(self._notebook, self.manager)
        self._notebook.add(self._status_tab, text="Registers & Log")

        # Service tab (PROG mode, calibration tools)
        ServiceTab = _get_service_tab()
        self._service_tab = ServiceTab(self._notebook, self.manager)
        self._notebook.add(self._service_tab, text="Service Tools")

        # Graph tab (battery voltage & charge over time)
        GraphTab = _get_graph_tab()
        self._graph_tab = GraphTab(self._notebook, self.manager)
        self._notebook.add(self._graph_tab, text="Graph")

        # --- Status bar ---
        status_frame = ttk.Frame(self.root, relief="sunken", padding=2)
        status_frame.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="Disconnected")
        ttk.Label(status_frame, textvariable=self._status_var,
                  font=("TkDefaultFont", 9)).pack(side="left", padx=5)

        self._model_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self._model_var,
                  font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=10)

        self._line_status_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self._line_status_var,
                  font=("TkDefaultFont", 9)).pack(side="right", padx=5)

        # Initial port scan
        self._refresh_ports()

    def _refresh_ports(self):
        """Refresh the list of available serial ports."""
        ports = scan_ports()
        port_names = [p[0] for p in ports]
        self._port_combo["values"] = port_names
        if port_names and not self._port_var.get():
            self._port_var.set(port_names[0])

    def _on_connect(self):
        """Connect to the selected serial port."""
        port = self._port_var.get()
        if not port:
            messagebox.showwarning("No Port", "Please select a serial port first.")
            return

        self._btn_connect.config(state="disabled")
        self._status_var.set(f"Connecting to {port}...")
        self.root.update_idletasks()

        # Show discovery progress modal
        self._discovery_modal = _DiscoveryModal(self.root)

        def on_discovery_progress(setting_name):
            """Called from worker thread — schedule UI update."""
            try:
                self.root.after(0, lambda n=setting_name:
                                self._discovery_modal.update_setting(n))
            except RuntimeError:
                pass

        self.manager.set_discovery_callback(on_discovery_progress)

        def do_connect():
            success = self.manager.connect(port)
            self.manager.set_discovery_callback(None)
            self.root.after(0, lambda: self._connect_done(success))

        threading.Thread(target=do_connect, daemon=True).start()

    def _connect_done(self, success: bool):
        """Handle connection result on the main thread."""
        # Dismiss discovery modal
        if hasattr(self, "_discovery_modal") and self._discovery_modal:
            self._discovery_modal.dismiss()
            self._discovery_modal = None

        if success:
            self.manager.start_polling()
            self._btn_connect.config(state="normal")
            self._btn_disconnect.config(state="normal")
            self._btn_pause.config(state="normal")
            self._polling_paused = False
            self._btn_pause.config(text="Pause Polling")
            self._status_var.set("Connected")
            self._main_tab.set_buttons_enabled(True)
            self._settings_tab.set_buttons_enabled(True)
            self._service_tab.set_buttons_enabled(True)
        else:
            self._btn_connect.config(state="normal")
            error = self.manager.state.last_error
            self._status_var.set(f"Connection failed: {error}")
            messagebox.showerror("Connection Failed",
                                 f"Could not connect to UPS:\n{error}")

    def _on_disconnect(self):
        """Disconnect from the UPS."""
        self.manager.disconnect()
        self._btn_disconnect.config(state="disabled")
        self._btn_pause.config(state="disabled")
        self._polling_paused = False
        self._btn_pause.config(text="Pause Polling")
        self._status_var.set("Disconnected")
        self._model_var.set("")
        self._line_status_var.set("")
        self._main_tab.set_buttons_enabled(False)
        self._settings_tab.set_buttons_enabled(False)
        self._service_tab.set_buttons_enabled(False)

    def _on_toggle_polling(self):
        """Toggle periodic polling on/off."""
        if self._polling_paused:
            self.manager.start_polling()
            self._polling_paused = False
            self._btn_pause.config(text="Pause Polling")
            self._status_var.set("Connected")
        else:
            self.manager.stop_polling()
            self._polling_paused = True
            self._btn_pause.config(text="Resume Polling")
            self._status_var.set("Connected (polling paused)")

    def _schedule_refresh(self):
        """Schedule periodic UI refresh."""
        if self._closing:
            return
        self._refresh_ui()
        self._refresh_after_id = self.root.after(
            self.REFRESH_INTERVAL, self._schedule_refresh)

    def _refresh_ui(self):
        """Update all UI elements from the current UPS state."""
        if not self.manager.state.connected:
            return

        state = self.manager.state.snapshot()

        # Update status bar
        model = state.get("model", "")
        self._model_var.set(model)

        status_hex = state.get("status_register", "00")
        from apc_ups.util.register_decoder import decode_status
        status_flags = decode_status(status_hex)
        if status_flags.get("On Line"):
            self._line_status_var.set("On Line")
        elif status_flags.get("On Battery"):
            self._line_status_var.set("ON BATTERY")
        else:
            self._line_status_var.set("")

        # Update tabs
        self._main_tab.update_display(state)
        self._settings_tab.update_display(state)
        self._status_tab.update_display(state)
        self._service_tab.update_display(state)
        self._graph_tab.update_display(state)

    def _on_message(self, timestamp: str, message: str):
        """Handle a message from the UPS manager (called from worker thread)."""
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._status_tab.add_message(timestamp, message))
        except RuntimeError:
            pass  # Root already destroyed

    def _on_alert(self, alert_char: str):
        """Handle an async alert from the UPS (called from worker thread)."""
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._status_tab.add_alert(alert_char))
        except RuntimeError:
            pass  # Root already destroyed

    def on_closing(self):
        """Clean shutdown — stop polling, close serial port, destroy window.

        Guards against re-entry (double-clicking the close button) and
        suppresses callbacks that would fire after the window is gone.
        """
        if self._closing:
            return
        self._closing = True

        # Prevent further WM_DELETE_WINDOW events
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Cancel the scheduled UI refresh
        if self._refresh_after_id is not None:
            self.root.after_cancel(self._refresh_after_id)
            self._refresh_after_id = None

        # Suppress manager callbacks so they don't touch dead widgets
        self.manager.set_message_callback(None)
        self.manager.set_alert_callback(None)

        # Disconnect (stops poll thread, flushes & closes serial port)
        self.manager.disconnect()

        self.root.destroy()


class _DiscoveryModal(tk.Toplevel):
    """Modal dialog showing setting value discovery progress during connect."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("Discovering Settings")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent closing

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Discovering firmware setting values...",
                  font=("TkDefaultFont", 10, "bold")).pack(pady=(0, 5))
        ttk.Label(frame, text="Cycling through each setting to detect\n"
                  "available values for this UPS model.",
                  foreground="gray40", justify="center").pack(pady=(0, 10))

        self._setting_var = tk.StringVar(value="Connecting...")
        ttk.Label(frame, textvariable=self._setting_var,
                  font=("Consolas", 10)).pack(pady=(0, 5))

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.grab_set()

    def update_setting(self, setting_name: str) -> None:
        """Update the currently-scanning setting name."""
        self._setting_var.set(f"Scanning: {setting_name}")

    def dismiss(self) -> None:
        """Close the modal."""
        self.grab_release()
        self.destroy()


def main():
    """Application entry point."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    root = tk.Tk()
    app = APCUPSApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
