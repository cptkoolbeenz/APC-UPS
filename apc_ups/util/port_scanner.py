"""Enumerate available serial ports."""

from serial.tools.list_ports import comports


def scan_ports() -> list[tuple[str, str]]:
    """Return a list of (port_device, description) for available serial ports.

    Sorted by port name for consistent ordering.
    """
    ports = []
    for port_info in sorted(comports(), key=lambda p: p.device):
        ports.append((port_info.device, port_info.description))
    return ports
