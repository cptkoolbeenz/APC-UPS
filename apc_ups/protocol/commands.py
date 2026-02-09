"""Command registry for APC UPS-Link protocol."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UPSCommand:
    """Definition of a single UPS-Link command."""
    char: str               # ASCII character(s) to send
    name: str               # Human-readable name
    response_format: str    # "numeric", "hex", "string", "date", "status", "none"
    unit: str = ""          # Display unit: "V", "%", "°C", "Hz", "min", "sec", "W"
    editable: bool = False  # Whether this setting can be changed via Edit command
    direct_edit: bool = False  # Whether editing uses direct character input (c, x)
    description: str = ""


# All documented UPS-Link commands
COMMANDS: dict[str, UPSCommand] = {
    # --- 3.1 UPS Control Commands ---
    "Y": UPSCommand("Y", "Set UPS to Smart Mode", "string",
                     description="Enter smart signaling mode. Response: SM"),
    "A": UPSCommand("A", "Test Lights and Beeper", "string",
                     description="Illuminate LEDs and sound beeper for 2s. Response: OK"),
    "K": UPSCommand("K", "Turn Off after Delay", "string",
                     description="K(>1.5s)K — Turn off UPS after shutdown delay"),
    "S": UPSCommand("S", "Shut Down UPS on Battery", "string",
                     description="Shut down on battery after shutdown delay. Response: OK"),
    "U": UPSCommand("U", "Simulate Power Failure", "string",
                     description="Brief transfer to battery. Response: OK"),
    "W": UPSCommand("W", "Battery Test", "string",
                     description="Run battery self-test (~8s). Response: OK"),
    "Z": UPSCommand("Z", "Turn Off UPS", "string",
                     description="Z(>1.5s)Z — Turn off UPS immediately"),
    "@": UPSCommand("@", "Shut Down with Delayed Wake Up", "string",
                    description="@ddd — Shut down then restart after ddd tenths of hour"),
    "\x7f": UPSCommand("\x7f", "Abort Shutdown", "string",
                       description="DEL — Abort @ddd, S, or K(>1.5s)K shutdown"),
    "D": UPSCommand("D", "Run Time Calibration", "string",
                     description="Start/abort runtime calibration. Response: OK or NO"),
    "^": UPSCommand("^", "UPS to Bypass", "string",
                    description="Toggle bypass mode. Response: BYP/INV/ERR"),
    "\x0e": UPSCommand("\x0e", "Turn UPS On", "string",
                       description="Ctrl+N(>1.5s)Ctrl+N — Turn on UPS"),
    "R": UPSCommand("R", "Return to Simple Mode", "string",
                     description="Exit smart mode. Response: BYE"),

    # --- 3.2 UPS Status Inquiry Commands ---
    "X": UPSCommand("X", "Battery Test Result", "string",
                     description="Last test result: OK/BT/NG/NO"),
    ">": UPSCommand(">", "Number of Battery Packs", "numeric", editable=True,
                     description="External battery packs connected"),
    "<": UPSCommand("<", "Number of Bad Battery Packs", "numeric",
                     description="Bad battery packs detected"),
    "G": UPSCommand("G", "Transfer Cause", "string",
                     description="Reason for last transfer to battery: R/H/L/T/O/S"),
    "V": UPSCommand("V", "Firmware Version", "string",
                     description="3-char firmware version (model, revision, voltage)"),
    "g": UPSCommand("g", "Nominal Battery Voltage Rating", "numeric", "V",
                     description="Nominal battery voltage: 024, 048, etc."),
    "f": UPSCommand("f", "Battery Capacity", "numeric", "%",
                     description="Remaining battery capacity as percent"),
    "9": UPSCommand("9", "Acceptable Line Quality", "string",
                     description="FF=acceptable, 00=unacceptable"),
    "Q": UPSCommand("Q", "UPS Status", "hex",
                     description="2-digit hex status register"),
    "~": UPSCommand("~", "State Register", "hex",
                     description="2-digit hex state register"),
    "'": UPSCommand("'", "Trip1 Register", "hex",
                     description="2-digit hex Trip1 fault register"),
    "8": UPSCommand("8", "Trip Register", "hex",
                     description="2-digit hex Trip register"),
    "7": UPSCommand("7", "DIP Switch Position", "hex",
                     description="2-digit hex DIP switch status"),
    "n": UPSCommand("n", "UPS Serial Number", "string",
                     description="Serial number (8-12 chars)"),
    "m": UPSCommand("m", "UPS Manufacture Date", "date",
                     description="Manufacture date dd/mm/yy"),
    "j": UPSCommand("j", "Run Time Remaining", "numeric", "min",
                     description="Estimated remaining runtime in minutes"),
    "y": UPSCommand("y", "Copyright", "string",
                     description="Returns (C) APCC to verify genuine APC product"),
    "a": UPSCommand("a", "All Commands Available", "string",
                     description="Lists all supported commands for this UPS"),
    "b": UPSCommand("b", "Version in Decimal", "string",
                     description="SKU.firmware_rev.country_code"),
    "\x01": UPSCommand("\x01", "UPS Model", "string",
                       description="Ctrl+A — UPS model name (up to 32 chars)"),

    # --- Undocumented Smart Constants (battery discharge curve) ---
    "0": UPSCommand("0", "Battery Constant (Runtime)", "string",
                     description="Battery discharge curve / runtime constant. "
                                 "Reset to default before runtime calibration."),
    "4": UPSCommand("4", "Battery Constant (Low)", "string",
                     description="Battery discharge curve constant (low). Model-specific."),
    "5": UPSCommand("5", "Battery Constant (Mid)", "string",
                     description="Battery discharge curve constant (mid). Model-specific."),
    "6": UPSCommand("6", "Battery Constant (High)", "string",
                     description="Battery discharge curve constant (high). Model-specific."),

    # --- 3.3 UPS Power Inquiry Commands ---
    "/": UPSCommand("/", "Load Current", "numeric", "A",
                     description="True RMS load current (Matrix-UPS only)"),
    "\\": UPSCommand("\\", "Apparent Load Power", "numeric", "%",
                      description="Output load as % of rated VA (Matrix-UPS only)"),
    "B": UPSCommand("B", "Battery Voltage", "numeric", "V",
                     description="Present battery voltage"),
    "C": UPSCommand("C", "UPS Internal Temperature", "numeric", "°C",
                     description="Internal operating temperature"),
    "F": UPSCommand("F", "Utility Operating Frequency", "numeric", "Hz",
                     description="Internal operating frequency"),
    "L": UPSCommand("L", "Line Voltage", "numeric", "V",
                     description="Present input line voltage"),
    "M": UPSCommand("M", "Maximum Line Voltage", "numeric", "V",
                     description="Max input voltage since last query"),
    "N": UPSCommand("N", "Minimum Line Voltage", "numeric", "V",
                     description="Min input voltage since last query"),
    "O": UPSCommand("O", "Output Voltage", "numeric", "V",
                     description="Present output voltage"),
    "P": UPSCommand("P", "Load Power", "numeric", "%",
                     description="Output load as % of rated Watts"),

    # --- 3.4 UPS Customizing Commands ---
    "\x1a": UPSCommand("\x1a", "Read All EEPROM Parameters", "string",
                       description="Ctrl+Z — All configurable EEPROM values"),
    "z": UPSCommand("z", "Reset UPS EEPROM Variables", "string",
                     description="Reset all EEPROM to factory defaults. Response: CLEAR"),
    "-": UPSCommand("-", "Edit", "string",
                     description="Cycle to next EEPROM value for preceding command"),
    "\x16": UPSCommand("\x16", "Output Voltage Selection", "string",
                       description="Ctrl+V — Output voltage reporting selection (Matrix-UPS)"),
    "\x0c": UPSCommand("\x0c", "Front Panel Language Selection", "string",
                       description="Ctrl+L — Display language (Matrix-UPS)"),
    "E": UPSCommand("E", "Automatic Battery Test", "string", "Hr", editable=True,
                     description="Self-test interval: 336/168/ON/OFF"),
    "c": UPSCommand("c", "UPS ID", "string", editable=True, direct_edit=True,
                     description="8-character UPS identifier"),
    "x": UPSCommand("x", "Battery Replacement Date", "date", editable=True, direct_edit=True,
                     description="Date battery was last replaced dd/mm/yy"),
    "u": UPSCommand("u", "Upper Transfer Voltage", "numeric", "V", editable=True,
                     description="Upper voltage threshold for transfer to battery"),
    "l": UPSCommand("l", "Lower Transfer Voltage", "numeric", "V", editable=True,
                     description="Lower voltage threshold for SmartBoost"),
    "e": UPSCommand("e", "Minimum Battery Capacity to Restart", "numeric", "%", editable=True,
                     description="Min battery % before UPS restarts after shutdown"),
    "o": UPSCommand("o", "Output Voltage", "numeric", "V", editable=True,
                     description="On-battery nominal output voltage setting"),
    "s": UPSCommand("s", "Utility Failure Sensitivity", "string", editable=True,
                     description="Sensitivity to voltage fluctuations: H/M/L"),
    "q": UPSCommand("q", "Low Battery Warning", "numeric", "min", editable=True,
                     description="Minutes before shutdown when low battery warning triggers"),
    "k": UPSCommand("k", "Audible Alarm", "string", editable=True,
                     description="Alarm behavior: 0/T/L/N"),
    "p": UPSCommand("p", "Shutdown Delay", "numeric", "sec", editable=True,
                     description="Delay in seconds between S/K command and actual shutdown"),
    "r": UPSCommand("r", "Turn On Delay", "numeric", "sec", editable=True,
                     description="Delay in seconds before UPS restarts after shutdown"),
}

# Commands polled at fast rate (every ~2s)
FAST_POLL_CMDS = ["f", "B", "P", "L", "O", "Q"]

# Commands polled at slow rate (every ~10s)
SLOW_POLL_CMDS = ["C", "F", "j", "M", "N"]

# Commands read once at connect time
ONCE_CMDS = [
    "\x01",  # Ctrl+A — Model
    "V",     # Firmware version
    "b",     # Version in decimal
    "n",     # Serial number
    "m",     # Manufacture date
    "g",     # Nominal battery voltage
    "y",     # Copyright
    "G",     # Transfer cause
    "X",     # Last test result
    ">",     # Battery packs
    "~",     # State register
    "'",     # Trip1 register
    "8",     # Trip register
    "7",     # DIP switch
    # Smart constants (undocumented battery discharge parameters)
    "0", "4", "5", "6",
    # Editable settings — read their current values
    "E", "c", "x", "u", "l", "e", "o", "s", "q", "k", "p", "r", ">",
]
