"""Protocol constants for APC UPS-Link communication."""

# Serial communication parameters
BAUD_RATE = 2400
BYTE_SIZE = 8
STOP_BITS = 1
PARITY = "N"  # None
FLOW_CONTROL = False
TIMEOUT = 3.0  # seconds for read timeout
WRITE_TIMEOUT = 3.0

# Protocol timing
TIMED_CMD_DELAY = 1.7  # seconds between K..K and Z..Z sequences
MIN_CMD_INTERVAL = 0.1  # minimum time between commands
EEPROM_WRITE_DELAY = 0.2  # seconds after an edit to allow EEPROM write to complete
POLL_FAST_INTERVAL = 2.0  # seconds
POLL_SLOW_INTERVAL = 10.0  # seconds

# Response terminator
RESPONSE_TERMINATOR = b"\r\n"

# Smart mode
SMART_MODE_CMD = "Y"
SMART_MODE_RESPONSE = "SM"

# Asynchronous alert characters (single char, NO \r\n)
ALERT_CHARS = frozenset("!$%+?=*#&|")

ALERT_DESCRIPTIONS = {
    "!": "Line Fail — UPS transferred to battery",
    "$": "Return from Line Fail — back on line power",
    "%": "Low Battery",
    "+": "Return from Low Battery — battery recharged",
    "?": "Abnormal Condition",
    "=": "Return from Abnormal Condition",
    "*": "UPS About to Turn Load Off",
    "#": "Replace Battery",
    "&": "Check Alarm Register for Fault",
    "|": "EEPROM Variable Change",
}

# UPS Status register (Q command) bit definitions — 2-digit hex
STATUS_BITS = {
    7: "Replace Battery",
    6: "Low Battery",
    5: "Overloaded Output",
    4: "On Battery",
    3: "On Line",
    2: "SmartBoost",
    1: "SmartTrim",
    0: "Runtime Calibration",
}

# State register (~ command) bit definitions — 2-digit hex
STATE_BITS = {
    7: "Ready to power load upon user command or return of normal line voltage",
    6: "Ready to power load upon user command",
    5: "In bypass mode as a result of manual bypass control",
    4: "Returning from bypass mode",
    3: "In bypass mode as a result of UPS-Link or key command",
    2: "Going to bypass mode as a result of UPS-Link or key command",
    1: "In bypass mode due to internal fault (TRIP or TRIP1 register)",
    0: "In wake up mode (startup test lasting less than 2 seconds)",
}

# Trip1 register (' command) bit definitions — 2-digit hex
TRIP1_BITS = {
    7: "Bad output voltage",
    6: "UPS fault — SmartBoost or SmartTrim relay fault",
    5: "UPS fault — commanded out of bypass with no batteries attached",
    4: "UPS fault — DC imbalance; UPS is in bypass",
    3: "UPS fault — output voltage select failure; UPS is in bypass",
    2: "UPS fault — bypass supply failure",
    1: "UPS fault — Isolation Unit fan failure",
    0: "UPS fault — Electronics Unit fan failure; UPS is in bypass",
}

# Trip register (8 command) bit definitions — 2-digit hex
TRIP_BITS = {
    7: "UPS fault — internal temperature exceeded nominal limits",
    6: "UPS fault — bypass relay malfunction",
    5: "UPS fault — battery charger failure",
    4: "UPS in shut down mode via 'S' command",
    3: "UPS in 'sleep' mode via '@ddd' command",
    2: "UPS fault — main relay malfunction; UPS turned off",
    1: "UPS unable to transfer to on-battery operation due to overload",
    0: "UPS output unpowered due to low battery shut down",
}

# Firmware version — 1st character model type mapping
FIRMWARE_MODEL_MAP = {
    "2": "Smart-UPS 250",
    "4": "Smart-UPS 400, UPS 370ci",
    "6": "Smart-UPS 600",
    "7": "Smart-UPS 900",
    "8": "Smart-UPS 1250",
    "9": "Smart-UPS 2000",
    "0": "Matrix-UPS 3000",
    "5": "Matrix-UPS 5000",
    "F": "Smart-UPS 450",
    "G": "Smart-UPS 700",
    "I": "Smart-UPS 1000",
    "K": "Smart-UPS 1400",
    "M": "Smart-UPS 2200",
    "O": "Smart-UPS 3000",
}

# Firmware version — 3rd character voltage version mapping
FIRMWARE_VOLTAGE_MAP = {
    "A": "100 Vac",
    "D": "120 Vac",
    "M": "208 Vac",
    "I": "220/230/240 Vac",
    "J": "200 Vac",
}

# Transfer cause codes (G command)
TRANSFER_CAUSE = {
    "R": "Unacceptable utility voltage rate of change",
    "H": "High utility voltage",
    "L": "Low utility voltage",
    "T": "Line voltage notch or spike",
    "O": "No transfers have occurred",
    "S": "UPS-Link command or self-test",
}

# Battery test results (X command)
TEST_RESULTS = {
    "OK": "Good battery",
    "BT": "Battery failed — insufficient capacity",
    "NG": "Invalid test — overload",
    "NO": "No test results available",
}

# Sensitivity settings (s command) for Smart-UPS
SENSITIVITY_VALUES = ["H", "M", "L", "L"]  # cycle order (L repeated for 4-slot EEPROM)
SENSITIVITY_LABELS = {
    "H": "High",
    "M": "Medium",
    "L": "Low",
}

# Alarm control settings (k command)
ALARM_VALUES = ["0", "T", "L", "N"]
ALARM_LABELS = {
    "0": "Immediate alarm (5 seconds)",
    "T": "30-second delay",
    "L": "Low battery only",
    "N": "Alarm disabled",
}

# Battery test interval (E command)
SELF_TEST_VALUES = ["336", "168", "ON ", "OFF"]
SELF_TEST_LABELS = {
    "336": "Every 336 hours (14 days)",
    "168": "Every 168 hours (7 days)",
    "ON ": "On startup",
    "OFF": "No automatic test",
}

# Low battery warning (q command)
LOW_BATTERY_WARNING_VALUES = ["02", "05", "07", "10"]

# Shutdown delay (p command)
SHUTDOWN_DELAY_VALUES = ["020", "180", "300", "600"]

# Turn on delay (r command)
TURN_ON_DELAY_VALUES = ["000", "060", "180", "300"]

# Minimum battery capacity to restart (e command) — newer Smart-UPS models
MIN_BATTERY_RESTART_VALUES = ["00", "15", "50", "90"]

# Output voltage (o command) — 220/230/240 Vac versions
OUTPUT_VOLTAGE_VALUES = ["225", "230", "240", "220"]

# Upper transfer voltage (u command) — 220/230/240 Vac version
UPPER_TRANSFER_220_VALUES = ["253", "264", "271", "280"]

# Lower transfer voltage (l command) — 220/230/240 Vac version
LOWER_TRANSFER_220_VALUES = ["196", "188", "208", "204"]

# Battery packs (> command) — raw byte value 0-255, edited via direct input
BATTERY_PACKS_MAX = 255

# PROG mode timing
PROG_MODE_DELAY = 4.0  # seconds between the two '1' characters
PROG_MODE_CMD = "1"
PROG_MODE_RESPONSE = "PROG"

# Temperature alert defaults
DEFAULT_TEMP_ALERT_THRESHOLD = 40.0  # °C — warn if internal temp exceeds this

# Battery age warning threshold
BATTERY_AGE_WARNING_DAYS = 730  # 2 years — suggest replacement
