# APC UPS Manager

A Python desktop application for monitoring and configuring APC Smart-UPS units via the UPS-Link serial protocol. Connects over RS-232 (or USB-serial adapter) at 2400 baud and provides real-time monitoring, full EEPROM setting management, register diagnostics, and service-level calibration tools.

Built as a modern, open-source replacement for the legacy **APCfix.exe** utility, with a safety-first design that prevents accidental changes to critical UPS parameters.

## Sources and Credits

- **APCfix.exe** — The original DOS/Windows UPS configuration tool that inspired this project. APCfix provided direct EEPROM access and register viewing for APC Smart-UPS units. This project replicates and extends its capabilities in a modern Python GUI.

- **UPS-Link Protocol Specification** (`UPS-Link_Protocol_Specification.pdf`) — APC's official protocol document covering all serial commands, response formats, register bit maps, and EEPROM editing procedures.

- **APC Smart-UPS XL Manual** (`apc-sua2200xli-ups-manual.pdf`) — Hardware reference manual for the Smart-UPS 2200 XL (SUA2200XL-I).

- **Community field-service guide** — Originally published at [ebastlirna.cz](http://www.ebastlirna.cz/modules.php?name=Forums&file=viewtopic&p=403435) (Czech electronics forum). Contains undocumented service procedures, PROG mode details, smart battery constants, and field calibration techniques that are not covered in APC's official documentation. Translated and adapted in `field_service_notes.md`.

- **Serial cable pinout** (`att_124.jpg`) — Wiring diagram for the APC 940-024C serial cable.

## Requirements

- Python 3.10+
- pyserial >= 3.5
- tkinter (included with most Python installations)
- RS-232 serial connection to the UPS (direct or via USB-serial adapter)

```
pip install -r requirements.txt
```

## Running

```
python run.py
```

## Project Structure

```
APC-UPS/
├── run.py                          Entry point
├── requirements.txt                Dependencies (pyserial)
├── field_service_notes.md          Community service guide (from ebastlirna.cz)
├── apc_ups/
│   ├── protocol/
│   │   ├── constants.py            Baud rate, timing, alert chars, register bit maps
│   │   ├── commands.py             Command registry (50+ UPS commands)
│   │   ├── serial_conn.py          Thread-safe pyserial wrapper
│   │   └── ups_protocol.py         Command send/receive, async alert filtering
│   ├── core/
│   │   ├── ups_manager.py          High-level orchestrator (connect, poll, settings)
│   │   ├── ups_state.py            Data model for all UPS values
│   │   ├── editable_settings.py    13 editable settings with allowed values
│   │   └── calibration.py          Battery runtime calibration state machine
│   ├── ui/
│   │   ├── app.py                  Main window, port selector, tab management
│   │   ├── main_tab.py             Monitor tab (live readings, action buttons)
│   │   ├── settings_tab.py         Settings tab (EEPROM editing)
│   │   ├── status_tab.py           Registers & Log tab (diagnostics)
│   │   ├── service_tab.py          Service Tools tab (PROG mode, calibration)
│   │   ├── dialogs.py              Three-tier confirmation dialogs
│   │   └── tooltip.py              Hover tooltip system
│   └── util/
│       ├── register_decoder.py     Hex register to bit flag decoding
│       └── port_scanner.py         Serial port enumeration
└── tests/
    ├── test_protocol.py            Protocol and mock UPS tests
    ├── test_register_decoder.py    Register decoder tests
    ├── test_editable_settings.py   Setting definitions and edit cycling tests
    └── mock_ups.py                 Simulated UPS for testing without hardware
```

---

## Application Guide

### Connection Bar

| Element | Description |
|---------|-------------|
| **Serial Port** dropdown | Lists all detected serial/COM ports on the system. |
| **Scan Ports** button | Re-scans for serial ports. Use after plugging in a USB-serial adapter. |
| **Connect** button | Opens the selected port, enters Smart Mode (`Y` command), and reads all UPS values. |
| **Disconnect** button | Stops monitoring and closes the serial connection. |

### Status Bar

The bottom bar shows three pieces of information:
- **Connection state** — "Disconnected", "Connecting to COMx...", or "Connected"
- **UPS model** — Model name reported by the UPS (bold)
- **Line status** — "On Line" or "ON BATTERY"

---

### Monitor Tab

The main monitoring tab with live readings updated every 2 seconds.

#### Left Panel — UPS Identity

| Field | Description |
|-------|-------------|
| **Model** | UPS model name (read via Ctrl+A command). |
| **Firmware** | 3-character firmware code: model type, revision, voltage class. |
| **Manufactured** | Date the UPS was manufactured (from EEPROM). |
| **Battery Replaced** | Date batteries were last replaced. Editable in the Settings tab. |
| **UPS Name** | 8-character user-assigned identifier. Editable in the Settings tab. |
| **Serial Number** | Factory serial number (read-only). |
| **Line Frequency** | Measured AC line frequency in Hz. Polled every ~10 seconds. |
| **Internal Temp** | Internal UPS temperature in Celsius. Polled every ~10 seconds. |
| **Battery System** | Nominal battery system voltage (e.g. 24V, 48V). |

#### Center Panel — Live Readings

| Element | Description |
|---------|-------------|
| **Firmware & Battery Constants** | Firmware version detail and the four undocumented smart constants (0, 4, 5, 6) that control battery discharge curve estimation. |
| **Temperature Alert Banner** | Red banner that appears when internal temperature exceeds the configured threshold (default 40 C). |
| **Battery Age Warning** | Gold banner that appears when battery age exceeds 2 years, suggesting replacement. |
| **Estimated Runtime** | Minutes of battery runtime remaining at the current load level. Polled every ~10 seconds. |
| **Battery Charge Level** | Progress bar and percentage showing remaining battery capacity. Must be 100% to start runtime calibration. |
| **Output Load** | Vertical progress bar showing load as percentage of rated capacity, plus estimated watts. Bar changes color from green to yellow to red as load increases. |
| **Input Voltage** | Vertical progress bar and value (0-300V scale) showing measured AC input voltage. Polled every ~2 seconds. |
| **Output Voltage** | Measured AC output voltage to connected equipment. Polled every ~2 seconds. |

#### Right Panel — Voltage and Battery Details

| Field | Description |
|-------|-------------|
| **Battery Voltage** | Present DC battery voltage. |
| **Battery Packs** | Number of external battery packs connected (0-16). Affects runtime calculation. |
| **Upper Transfer** | Input voltage above which the UPS transfers to battery. |
| **Lower Transfer** | Input voltage below which SmartBoost engages. |
| **Output Setting** | Nominal output voltage when running on battery. |
| **Peak Input** | Maximum input voltage recorded since last poll. Resets each time it is read. |
| **Lowest Input** | Minimum input voltage recorded since last poll. Resets each time it is read. |

#### Action Buttons

| Button | Description |
|--------|-------------|
| **Run Battery Test** | Runs an automatic battery self-test (~8 seconds). The UPS briefly switches to battery power and back. Result appears in the Registers & Log tab. |
| **Test Indicators** | Flashes all front-panel LEDs and sounds the beeper for about 2 seconds. Safe diagnostic check. |
| **Toggle Bypass** | Switches between normal and bypass mode. In bypass mode, the load is fed directly from mains — the UPS is NOT protecting connected equipment. |
| **Meter Comparison** | Opens a dialog to compare UPS voltage readings against an external voltmeter. Enter your meter readings for input, output, and/or battery voltage to see the delta. |

#### Transfer Cause

Displays the reason the UPS last transferred to battery power:

| Code | Meaning |
|------|---------|
| R | Unacceptable utility voltage rate of change |
| H | High utility voltage |
| L | Low utility voltage |
| T | Line voltage notch or spike |
| O | No transfers have occurred |
| S | UPS-Link command or self-test |

---

### Settings Tab

#### Left Panel — UPS Identity (Read-Only)

Displays the same identity fields as the Monitor tab (model, firmware, serial number, etc.) plus a safety warning that all setting changes are written to EEPROM and take effect immediately.

#### Right Panel — Editable Settings

Each setting is shown as a row with the current value and a **Change** button. Clicking Change opens a confirmation dialog appropriate to the setting's danger level.

| Setting | Command | Allowed Values | Danger Level |
|---------|---------|----------------|--------------|
| **Low Battery Warning** | `q` | 02, 05, 07, 10 minutes | Normal |
| **Shutdown Delay** | `p` | 020, 180, 300, 600 seconds | Caution |
| **Turn On Delay** | `r` | 000, 060, 180, 300 seconds | Caution |
| **Self-Test Interval** | `E` | 336 hrs, 168 hrs, On startup, Off | Normal |
| **Min Battery for Restart** | `e` | 0%, 15%, 50%, 90% | Caution |
| **Sensitivity** | `s` | High, Medium, Low | Caution |
| **Alarm Control** | `k` | Immediate, 30s delay, Low battery only, Disabled | Normal |
| **Upper Transfer Voltage** | `u` | 253, 264, 271, 280 V | Caution |
| **Lower Transfer Voltage** | `l` | 196, 188, 208, 204 V | Caution |
| **Output Voltage Setting** | `o` | 220, 225, 230, 240 V | Caution |
| **Battery Packs** | `>` | 0 through 16 | Caution |
| **UPS ID** | `c` | 8-character free text | Normal |
| **Battery Replacement Date** | `x` | Date in dd/mm/yy format | Normal |

#### Factory Reset Settings

Resets ALL UPS EEPROM settings to factory defaults. Transfer voltages, sensitivity, delays, alarms, and self-test interval are all reverted. UPS ID and battery date are NOT affected. Requires typing "YES" to confirm (Dangerous tier).

---

### Registers & Log Tab

#### Register Panels

Four panels of read-only checkboxes showing the decoded bits of each UPS register. Registers are refreshed during normal polling.

**State Register (~)** — Bypass and ready states:
- In Wakeup mode
- Ready to power load
- In bypass (manual / UPS-Link / internal fault)
- Returning from bypass
- Going to bypass
- Ready on return of line power

**Trip1 Register (')** — Fault conditions causing bypass:
- Bad output voltage
- SmartBoost/SmartTrim relay fault
- Bypass supply failure
- DC imbalance
- Output voltage select failure
- Fan failure (electronics unit / isolation unit)

**Trip Register (8)** — Critical faults:
- Temperature exceeded
- Bypass relay malfunction
- Battery charger failure
- In shutdown mode
- In sleep mode
- Main relay malfunction
- Overload on battery failure
- Low battery shutdown

**Status Register (Q)** — Current operating state:
- Replace Battery
- Battery Low
- Overloaded Output
- On Battery
- On Line
- SmartBoost active
- SmartTrim active
- Runtime calibration occurred

#### Event Log

Dark-background scrolling log with green text showing timestamped messages and asynchronous UPS alerts. Alerts include:

| Alert | Meaning |
|-------|---------|
| `!` | Line Fail — UPS transferred to battery |
| `$` | Return from Line Fail — back on line power |
| `%` | Low Battery — capacity critically low |
| `+` | Return from Low Battery — battery recharged |
| `?` | Abnormal Condition — UPS fault |
| `=` | Return from Abnormal Condition — fault cleared |
| `*` | About to Turn Load Off — imminent shutdown |
| `#` | Replace Battery — battery needs replacement |
| `&` | Check Alarm Register — refer to Trip/Trip1 registers |
| `\|` | EEPROM Variable Change — a setting was modified |

---

### Service Tools Tab

Advanced tools for field service technicians. A warning banner reminds that incorrect calibration can damage equipment.

#### PROG Mode (Voltage Calibration)

An undocumented APC service mode that allows fine-tuning the internal voltage measurement calibration stored in EEPROM. The workflow is: Enter PROG > Select measurement > Read > Nudge +/- > Save > Exit.

| Element | Description |
|---------|-------------|
| **Measurement** selector | Choose which voltage to calibrate: L (Input), O (Output), or B (Battery). |
| **Current Reading** | Displays the UPS voltage reading in PROG mode. Compare against an external voltmeter. |
| **Enter PROG** | Enters PROG mode. Sends "1", waits 4 seconds, sends "1" again. Polling pauses. |
| **Nudge +** | Increases the calibration value by one step. |
| **Nudge -** | Decreases the calibration value by one step. |
| **Read** | Reads the current voltage value for the selected measurement type. |
| **Save to EEPROM** | Writes the adjusted calibration value to EEPROM permanently. Sends the "R" (Record) command. |
| **Exit PROG** | Exits PROG mode (sends ESC). Unsaved changes are discarded. Polling resumes. |

#### Temperature Monitoring

| Element | Description |
|---------|-------------|
| **Current temperature** | Internal UPS temperature in Celsius. |
| **Alert threshold** | Temperature above which a red warning banner appears on the Monitor tab. Default is 40 C. Session-only setting (not stored on UPS). |
| **Apply Threshold** | Applies the entered threshold value. |
| **Temperature history** | Session statistics: reading count, average, minimum, and maximum temperature since connection. Keeps up to 360 readings (~1 hour at 10-second intervals). |

#### Runtime Calibration Pre-Check

Displays values that should be reviewed before starting a runtime calibration (`D` command):

| Field | Description |
|-------|-------------|
| **Constant 0 (Runtime)** | Battery discharge curve runtime constant. Should be at factory default before calibrating. A warning appears if it differs. |
| **Constant 4 (Low)** | Discharge curve parameter (low range). Factory-set. |
| **Constant 5 (Mid)** | Discharge curve parameter (mid range). Factory-set. |
| **Constant 6 (High)** | Discharge curve parameter (high range). Factory-set. |
| **Battery status** | Shows current charge percentage and whether the battery is ready for calibration (must be 100%). |

---

## Safety Model

All write operations use a three-tier confirmation system to prevent accidental changes.

### Normal (Green)

Simple "Are you sure?" dialog with Cancel and Apply buttons. Used for low-risk operations:
- Self-test, LED/alarm test
- UPS ID change, battery date change
- Self-test interval, alarm control

### Caution (Yellow)

Yellow warning banner: "CAUTION: This changes UPS behavior." Cancel button is focused by default. Used for settings that affect UPS protection behavior:
- Transfer voltages (upper/lower)
- Sensitivity, shutdown delay, wake-up delay
- Minimum battery for restart, output voltage
- Battery packs

### Dangerous (Red)

Red warning banner with a text field requiring the user to type "YES" before the Execute button enables. Used for:
- Factory reset (EEPROM wipe)
- Runtime calibration
- Shutdown commands (K..K, Z..Z, S)

### Additional Safeguards

- No keyboard shortcuts for write operations — all require mouse clicks
- All Change buttons are disabled while a setting change is in progress
- All write operations are logged with timestamp in the Event Log
- Polling pauses automatically during any write operation to prevent bus contention

---

## Protocol Details

- **Baud rate:** 2400, 8N1, no flow control
- **Smart Mode:** Send `Y` → expect `SM\r\n`
- **Commands:** Single ASCII character, responses terminated with `\r\n`
- **Async alerts:** Single character (`! $ % + ? = * # & |`), no terminator
- **Timed commands** (K, Z): Two identical characters with >1.5 second delay between them
- **Edit cycling:** Send command char to read current value, then `-` to advance EEPROM to next value in the allowed set
- **Direct edit** (c, x): Send command, `-`, then type 8 characters, expect `OK`
- **PROG mode:** Send `1`, wait 4 seconds, send `1` → expect `PROG`. Use `+`/`-` to adjust, `R` to save, `ESC` to exit.

---

## Testing

Run the test suite (46 tests):

```
python -m unittest discover -s tests -v
```

Tests cover:
- Protocol command encoding and response parsing
- Mock UPS simulation (Smart Mode, commands, edit cycling, PROG mode)
- Register bit decoding (status, state, trip, trip1)
- Editable setting definitions, allowed values, and edit cycle counting
- Smart constants and PROG mode sequences
- Battery age computation and calibration pre-checks

---

## Known Issues

- **CH340 USB-serial adapter reconnection:** After using the Disconnect button, clicking Connect again may fail with `PermissionError(13, 'A device attached to the system is not functioning.')`. This is a Windows driver issue where the CH340 chipset does not fully release the COM port after close. **Workaround:** Unplug and re-plug the USB-serial adapter, then click Connect. Other USB-serial chipsets (FTDI, CP2102) are not known to have this issue.

---

## License

This project is provided as-is for personal and educational use. The UPS-Link protocol specification is proprietary to APC/Schneider Electric.
