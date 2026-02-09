"""Editable setting definitions with allowed values and edit cycling."""

from dataclasses import dataclass
from enum import Enum


class DangerLevel(Enum):
    NORMAL = "normal"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


@dataclass
class EditableSetting:
    """Definition of an editable UPS EEPROM setting."""
    cmd_char: str           # Protocol command character
    name: str               # Human-readable name
    unit: str               # Display unit
    allowed_values: list[str]  # Ordered cycle of allowed values
    labels: dict[str, str]  # Value -> display label mapping
    danger: DangerLevel
    state_key: str          # Attribute name in UPSState
    direct_edit: bool = False  # Whether editing uses direct character input
    description: str = ""


# All editable settings
SETTINGS: dict[str, EditableSetting] = {
    "self_test_interval": EditableSetting(
        cmd_char="E",
        name="Self Test Interval",
        unit="Hr",
        allowed_values=["336", "168", "ON ", "OFF"],
        labels={
            "336": "Every 336 hours (14 days)",
            "168": "Every 168 hours (7 days)",
            "ON ": "On startup",
            "OFF": "No automatic test",
        },
        danger=DangerLevel.NORMAL,
        state_key="self_test_interval",
        description="How often the UPS runs an automatic battery self-test.",
    ),
    "alarm_control": EditableSetting(
        cmd_char="k",
        name="Alarm Control",
        unit="",
        allowed_values=["0", "T", "L", "N"],
        labels={
            "0": "Immediate (5 sec delay)",
            "T": "30-second delay",
            "L": "Low battery only",
            "N": "Disabled",
        },
        danger=DangerLevel.NORMAL,
        state_key="alarm_control",
        description="Controls when the audible alarm sounds.",
    ),
    "ups_id": EditableSetting(
        cmd_char="c",
        name="UPS ID",
        unit="",
        allowed_values=[],  # Free text, 8 chars
        labels={},
        danger=DangerLevel.NORMAL,
        state_key="ups_id",
        direct_edit=True,
        description="8-character identifier stored in UPS EEPROM.",
    ),
    "battery_replace_date": EditableSetting(
        cmd_char="x",
        name="Battery Replacement Date",
        unit="",
        allowed_values=[],  # Free text, dd/mm/yy
        labels={},
        danger=DangerLevel.NORMAL,
        state_key="battery_replace_date",
        direct_edit=True,
        description="Date batteries were last replaced (dd/mm/yy).",
    ),
    "low_battery_warning": EditableSetting(
        cmd_char="q",
        name="Low Battery Warning",
        unit="Min",
        allowed_values=["02", "05", "07", "10"],
        labels={
            "02": "2 minutes",
            "05": "5 minutes",
            "07": "7 minutes",
            "10": "10 minutes",
        },
        danger=DangerLevel.CAUTION,
        state_key="low_battery_warning",
        description="Minutes of warning before UPS shuts down on low battery.",
    ),
    "shutdown_delay": EditableSetting(
        cmd_char="p",
        name="Shutdown Delay",
        unit="Sec",
        allowed_values=["020", "180", "300", "600"],
        labels={
            "020": "20 seconds",
            "180": "180 seconds",
            "300": "300 seconds",
            "600": "600 seconds",
        },
        danger=DangerLevel.CAUTION,
        state_key="shutdown_delay",
        description="Delay between shutdown command and actual power off.",
    ),
    "turn_on_delay": EditableSetting(
        cmd_char="r",
        name="Wake Up Delay",
        unit="Sec",
        allowed_values=["000", "060", "180", "300"],
        labels={
            "000": "No delay",
            "060": "60 seconds",
            "180": "180 seconds",
            "300": "300 seconds",
        },
        danger=DangerLevel.CAUTION,
        state_key="turn_on_delay",
        description="Delay before UPS restarts after a shutdown.",
    ),
    "min_battery_restart": EditableSetting(
        cmd_char="e",
        name="Min Battery to Restart",
        unit="%",
        allowed_values=["00", "15", "50", "90"],
        labels={
            "00": "0% (restart immediately)",
            "15": "15%",
            "50": "50%",
            "90": "90%",
        },
        danger=DangerLevel.CAUTION,
        state_key="min_battery_restart",
        description="Minimum battery capacity before UPS restarts after shutdown.",
    ),
    "sensitivity": EditableSetting(
        cmd_char="s",
        name="Sensitivity",
        unit="",
        allowed_values=["H", "M", "L", "L"],  # L repeated for 4-slot EEPROM
        labels={
            "H": "High",
            "M": "Medium",
            "L": "Low",
        },
        danger=DangerLevel.CAUTION,
        state_key="sensitivity",
        description="How sensitive the UPS is to utility voltage fluctuations.",
    ),
    "upper_transfer_voltage": EditableSetting(
        cmd_char="u",
        name="Upper Transfer Voltage",
        unit="V",
        allowed_values=["253", "264", "271", "280"],  # 220/230/240 Vac defaults
        labels={
            "253": "253 V",
            "264": "264 V",
            "271": "271 V",
            "280": "280 V",
        },
        danger=DangerLevel.CAUTION,
        state_key="upper_transfer_voltage",
        description="Input voltage above which the UPS transfers to battery.",
    ),
    "lower_transfer_voltage": EditableSetting(
        cmd_char="l",
        name="Lower Transfer Voltage",
        unit="V",
        allowed_values=["196", "188", "208", "204"],  # 220/230/240 Vac defaults
        labels={
            "196": "196 V",
            "188": "188 V",
            "208": "208 V",
            "204": "204 V",
        },
        danger=DangerLevel.CAUTION,
        state_key="lower_transfer_voltage",
        description="Input voltage below which SmartBoost engages.",
    ),
    "output_voltage_setting": EditableSetting(
        cmd_char="o",
        name="Output Voltage",
        unit="V",
        allowed_values=["225", "230", "240", "220"],
        labels={
            "225": "225 V",
            "230": "230 V",
            "240": "240 V",
            "220": "220 V",
        },
        danger=DangerLevel.CAUTION,
        state_key="output_voltage_setting",
        description="Nominal on-battery output voltage.",
    ),
    "battery_packs": EditableSetting(
        cmd_char=">",
        name="External Battery Packs",
        unit="",
        allowed_values=["000", "001", "002", "003", "004", "005",
                        "006", "007", "008", "009", "010", "011",
                        "012", "013", "014", "015", "016"],
        labels={
            "000": "0 (no external packs)",
            "001": "1 pack",
            "002": "2 packs",
            "003": "3 packs",
            "004": "4 packs",
            "005": "5 packs",
            "006": "6 packs",
            "007": "7 packs",
            "008": "8 packs",
            "009": "9 packs",
            "010": "10 packs",
            "011": "11 packs",
            "012": "12 packs",
            "013": "13 packs",
            "014": "14 packs",
            "015": "15 packs",
            "016": "16 packs",
        },
        danger=DangerLevel.CAUTION,
        state_key="battery_packs",
        description="Number of external battery packs connected. "
                    "Affects runtime calculation. Must match physical hardware.",
    ),
}


def count_edits_needed(setting: EditableSetting, current: str, target: str) -> int | None:
    """Calculate how many Edit ('-') commands are needed to cycle from current to target.

    Returns None if the target value is not in the allowed_values list.
    For settings where the value appears multiple times (like sensitivity 'L'),
    returns the minimum number of edits to reach the first occurrence.
    """
    values = setting.allowed_values
    if not values:
        return None
    if target not in values:
        return None

    # Find the current value's position
    try:
        current_idx = values.index(current)
    except ValueError:
        # Current value not in known list — try cycling from position 0
        current_idx = 0

    # Find the target — count forward from current
    n = len(values)
    for steps in range(1, n + 1):
        idx = (current_idx + steps) % n
        if values[idx] == target:
            return steps

    return None  # Should not happen if target is in values
