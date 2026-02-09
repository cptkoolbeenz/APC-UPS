# APC Smart-UPS Field Service Notes

> **Source:** Community field-service guide originally published at
> [ebastlirna.cz](http://www.ebastlirna.cz/modules.php?name=Forums&file=viewtopic&p=403435)
> (Czech electronics forum). Translated and adapted for reference here.

Findings from community and field-service documentation, cross-referenced against
our application's current capabilities. This document is intended as a practical
reference for anyone maintaining APC Smart-UPS units with our software.

---

## 1. Battery Life and Temperature Effects

### Community Findings

| Condition | Internal Temp | Expected Battery Life |
|---|---|---|
| Open desk, 25 C room | 34--36 C | ~6 years |
| Open desk, 35 C ambient (or enclosed cabinet) | ~45 C | ~1.5 years |
| Enclosed cabinet in summer | >50 C | <1 year |

Key observations:

- Battery life halves for every 10 C increase above 25 C.
- At 45 C and above, battery brand is irrelevant --- all fail within two years.
- An 80x80x40 mm Sunon fan (15--20 W) reduced idle temperature from 34--36 C down
  to 24--26 C, and limited battery-discharge temperature rise to 2 C (versus 46 C
  without cooling).
- Fan should be powered from UPS input (mains side), not the UPS output, to avoid
  draining the battery during an outage.

### Application Support

| Capability | Status | Detail |
|---|---|---|
| Read internal temperature (C command) | **Supported** | Polled every ~10 s (slow poll). Displayed in the UI as `temperature`. |
| Temperature trend / logging | **Supported** | Session-based history (up to 360 readings, ~1 hour at 10s intervals). Min/max/average summary shown in Service tab. |
| High-temperature alert | **Supported** | Configurable threshold (default 40 C) in Service tab. Red warning banner in main tab when exceeded. Alert logged to status messages. |
| Battery age tracking | **Supported** | The `battery_replace_date` (x command) is editable. Users can record the date batteries were last replaced. |

### Potential Enhancements

- Add a configurable high-temperature warning threshold (e.g., alert if C > 40 C).
- Add persistent temperature logging so users can identify enclosure heat problems
  before batteries are damaged.
- Surface a "battery age" indicator computed from `battery_replace_date` and the
  temperature history, so users get a proactive replacement reminder.

---

## 2. Voltage Calibration (PROG Mode)

### Community Findings

**Input Voltage Calibration:**

1. Read input voltage with the L command.
2. Compare against an external voltmeter; should agree within 5 V.
3. Enter PROG mode: send `1`, wait 4 seconds, send `1` again. UPS responds `PROG`.
4. Use `+` / `-` to adjust the reported value to match the external meter.
5. Press `R` to save the corrected value to EEPROM.

**Output Voltage (O command):**

- Cannot be fine-tuned via PROG mode.
- If the reading is off by more than 5 V from external measurement, suspect a
  hardware fault.

**Load Power (P command):**

- Verify against an external wattmeter.
- For SU700, 100% load equals approximately 400 W.

**Battery Voltage (B command):**

- Should match a DC voltmeter across the battery terminals.
- Set the B value 1--2 tenths of a volt higher than the voltmeter reading to
  prevent overcharging.

### Application Support

| Capability | Status | Detail |
|---|---|---|
| Read input voltage (L command) | **Supported** | Fast-polled every ~2 s. |
| Read output voltage (O command) | **Supported** | Fast-polled every ~2 s. |
| Read load power (P command) | **Supported** | Fast-polled every ~2 s. Load watts computed from model rating via `MODEL_WATTAGE` table. |
| Read battery voltage (B command) | **Supported** | Fast-polled every ~2 s. |
| PROG mode entry (`1` ... 4 s ... `1`) | **Supported** | Service tab: Enter PROG button with confirmation dialog. |
| PROG mode `+`/`-` adjustment | **Supported** | Service tab: +/- buttons adjust value in real-time. |
| PROG mode `R` save to EEPROM | **Supported** | Service tab: Save (R) button with confirmation. Context-separated from standard R command. |
| Nominal wattage lookup per model | **Supported** | `MODEL_WATTAGE` dictionary in `ups_manager.py` covers models from 250 through 3000. |

### Potential Enhancements

- Consider adding a dedicated "Service / Calibration" panel that implements the
  PROG mode protocol sequence. This would need:
  - The `1`-wait-`1` handshake with a 4-second timer.
  - `+`/`-` adjustment commands with live readback.
  - `R` to save, with clear warnings about EEPROM writes.
  - Strong UI guards (confirmation dialogs, danger labels) since incorrect
    calibration can cause overcharging or incorrect transfer behavior.
- Add a voltage comparison helper that lets the user enter their external meter
  reading and shows the delta.

---

## 3. Runtime Calibration

### Community Findings

- Battery must be at 100% charge. Ideally calibrate the day after installing fresh
  batteries so the battery has time to fully charge.
- Before calibrating, set item `0` (battery constant / runtime constant) to its
  default value.
- Send the `D` command to start. The UPS discharges under load until battery
  voltage drops to approximately 22 V (for 24 V nominal systems).
- Battery constants (smart constant items `4`, `5`, `6`) are model-specific
  discharge curve parameters. These are not in the official UPS-Link specification.
- Reference runtimes for SU700 at 150 W load:
  - 12 V 7 Ah batteries: 20--25 minutes.
  - 12 V 9 Ah batteries: 30--35 minutes.

### Application Support

| Capability | Status | Detail |
|---|---|---|
| Runtime calibration start/abort (D command) | **Supported** | Full state machine in `CalibrationManager` (IDLE -> CHECKING -> RUNNING -> COMPLETED/ABORTED/FAILED). |
| 100% battery check before start | **Supported** | `can_start()` enforces `battery_pct >= 100.0`. |
| Calibration progress tracking | **Supported** | `progress_pct` computes estimated progress as battery drains from 100% to ~25%. |
| Calibration abort | **Supported** | Sends D again to abort; transitions to ABORTED state. |
| Read battery constant `0` | **Supported** | Command `0` added to registry. Displayed in Smart Constants panel and Service tab. |
| Set battery constant `0` to default | **Not supported** | No write path for this undocumented constant (would require PROG mode per-value targeting). |
| Read smart constants `4`, `5`, `6` | **Supported** | Commands `4`, `5`, `6` added to registry. Displayed in Smart Constants panel and Service tab. |
| Write smart constants `4`, `5`, `6` | **Not supported** | These are undocumented, model-specific parameters. |
| Runtime remaining display | **Supported** | Command `j` is slow-polled; shown as `runtime_remaining` in minutes. |

### Potential Enhancements

- Add commands `0`, `4`, `5`, `6` to the command registry as read-only "smart
  constants" so users can inspect them.
- Add a pre-calibration checklist in the UI: verify 100% charge, display current
  battery constant `0`, and warn if it has been modified from the default.
- Provide model-specific reference runtime tables so users can compare their
  calibration result against expected values.

---

## 4. PROG Mode Details

### Community Findings

PROG mode is a service/calibration mode that is **not part of the standard
UPS-Link protocol specification**. It is entered by:

1. Sending `1` (ASCII 0x31).
2. Waiting exactly 4 seconds.
3. Sending `1` again.
4. UPS responds with `PROG`.

Once in PROG mode:

- `+` and `-` adjust the value of the currently selected parameter.
- `R` saves the changed value to EEPROM (different from the standard `R` = "return
  to simple mode" behavior).
- This mode allows calibration of voltage readings and other internal parameters
  that cannot be changed through the normal Edit (`-`) cycling mechanism.

### Application Support

| Capability | Status | Detail |
|---|---|---|
| PROG mode entry | **Supported** | Service tab with confirmation dialog. |
| PROG mode value adjustment | **Supported** | +/- buttons in Service tab. |
| PROG mode EEPROM save | **Supported** | Save (R) button with confirmation in Service tab. |
| Standard Edit cycling for EEPROM settings | **Supported** | Full implementation with `count_edits_needed()`, verification read-back, and all 12 editable settings. |
| EEPROM factory reset (z command) | **Supported** | Sends `z`, expects `CLEAR`, then re-reads all settings. |

### Potential Enhancements

- If PROG mode support is added, it must be clearly separated from the standard
  Edit workflow. The command character `R` has a different meaning in each context.
- Consider a "service mode" feature gate that must be explicitly enabled, since
  PROG mode changes can affect UPS safety behavior.

---

## 5. Smart Constants (Undocumented Commands)

### Community Findings

| Command | Description | Notes |
|---|---|---|
| `0` | Battery discharge curve / runtime constant | Should be reset to default before runtime calibration. |
| `4` | Battery discharge curve constant (low) | Model-specific. |
| `5` | Battery discharge curve constant (mid) | Model-specific. |
| `6` | Battery discharge curve constant (high) | Model-specific. |

These commands are confirmed to work across multiple Smart-UPS models. They are
used internally by the UPS firmware to compute runtime estimates from the battery
discharge curve. All other standard commands documented in the UPS-Link spec match
our implementation.

### Application Support

| Capability | Status | Detail |
|---|---|---|
| Standard command set (Y, A, K, S, U, W, Z, etc.) | **Supported** | All documented UPS-Link commands are in `COMMANDS` registry. |
| Inquiry commands (B, C, F, L, M, N, O, P, Q, etc.) | **Supported** | Full coverage with fast/slow polling and one-time reads. |
| Editable settings (E, c, x, u, l, e, o, s, q, k, p, r) | **Supported** | 12 editable settings with cycle-edit and direct-edit modes. |
| Smart constant `0` | **Supported** | Read-only, displayed in UI. |
| Smart constants `4`, `5`, `6` | **Supported** | Read-only, displayed in UI. |

### Potential Enhancements

- Add `0`, `4`, `5`, `6` as read-only commands in the `COMMANDS` dict with
  `response_format="numeric"`.
- Display them in a "Smart Constants" section of the UI, clearly labeled as
  undocumented / model-specific.
- Do **not** make them editable through the standard Edit path unless PROG mode is
  fully implemented and tested.

---

## 6. Hardware Repair Notes

### Community Findings

Common failure modes on Smart-UPS boards (not applicable to software, but
important context for field service):

| Component | Failure Mode | Replacement Part |
|---|---|---|
| Electrolytic capacitors (22 uF / 16 V) | Dry out, causing driver circuit failure | Replace all electrolytics preventively |
| Power FETs (IRFZ46, IRFP50N06) | Destruction (often caused by dried caps) | Direct replacement |
| Small-signal transistors (2N2222 / 2N2907) | Fail in driver pairs | Replace in matched pairs |
| MOSFET drivers (2N7000) | Fail alongside power FETs | Direct replacement |
| Logic ICs (4010, 74C14) | Damaged by overcurrent events | Direct replacement |
| Faston connectors | Corrosion, loose fit | Inspect and re-crimp |
| Transformer connector | Oxidation, poor contact | Clean or replace |
| Relays | Welded contacts, coil failure | Direct replacement |
| CPU socket | Poor contact from thermal cycling | Re-seat or replace socket |

### Application Support

| Capability | Status | Detail |
|---|---|---|
| Fault register decoding (Q, ~, ', 8) | **Supported** | Status, State, Trip1, and Trip registers are read and decoded. Can help identify whether a hardware fault is present. |
| Transfer cause logging (G command) | **Supported** | Captures reason for last transfer (R/H/L/T/O/S). |
| Self-test / battery test (W command) | **Supported** | Can identify battery or circuit failures. |
| Board-level hardware diagnosis | **Outside scope** | Software cannot diagnose individual component failures. This requires bench testing with a multimeter and oscilloscope. |

### Practical Notes

- If a UPS consistently fails self-tests (X returns NG) after battery replacement,
  suspect board-level component failure -- particularly dried electrolytics.
- If transfer cause (G) repeatedly shows unexpected values, check relay contacts
  and FET health.
- Our app can serve as a diagnostic aid by monitoring registers and test results
  over time, but it cannot replace hands-on hardware inspection.

---

## Summary: Coverage Matrix

| Topic | Fully Supported | Partially Supported | Not Supported / Out of Scope |
|---|---|---|---|
| **Temperature monitoring** | Read temp (C), threshold alert, session history | -- | Persistent log across sessions |
| **Battery age tracking** | Battery replace date (x), proactive age warning | -- | -- |
| **Input voltage reading** | L command, fast poll, PROG mode calibration | -- | -- |
| **Output voltage reading** | O command, fast poll, PROG mode calibration | -- | -- |
| **Battery voltage reading** | B command, fast poll, PROG mode calibration | -- | -- |
| **Load power reading** | P command + wattage calc | -- | -- |
| **Runtime calibration** | D command, full state machine, pre-check with constant 0 | -- | Resetting constant 0 to default |
| **Editable EEPROM settings** | 13 settings (incl. battery packs), cycle + direct edit | -- | -- |
| **EEPROM factory reset** | z command | -- | -- |
| **PROG mode** | Full: enter, +/- adjust, save, exit | -- | -- |
| **Smart constants (0, 4, 5, 6)** | Read-only display in UI and Service tab | -- | Write/edit (requires PROG mode per value) |
| **Voltage comparison** | Compare UPS vs external meter, show delta | -- | -- |
| **Fault register decoding** | Q, ~, ', 8 registers | -- | -- |
| **Hardware board repair** | -- | Fault registers aid diagnosis | Board-level repair is outside scope |

---

## Implementation Status

All items from the original "Recommended Priority" list have been implemented:

1. **DONE -- Smart constants (read-only):** Commands `0`, `4`, `5`, `6` added to
   command registry and polled at connect time. Displayed in Smart Constants panel
   (main tab) and Service tab calibration pre-check section.

2. **DONE -- Temperature alerting:** Configurable threshold (default 40 C) in
   Service tab. Red warning banner appears in main tab when temperature exceeds
   threshold. Alert messages logged.

3. **DONE -- Calibration pre-checks:** Battery constant `0` displayed in Service
   tab before calibration. Warning shown if constant differs from default.
   Battery percentage check displayed.

4. **DONE -- Temperature logging:** Session-based history (up to 360 readings).
   Min/max/average summary displayed in Service tab. History resets on disconnect.

5. **DONE -- PROG mode support:** Full implementation in Service tab with enter,
   +/- adjust, read, save (R), and exit. Confirmation dialogs and warning banners
   protect against accidental changes.

6. **DONE -- Voltage comparison tool:** Dialog in main tab (Compare Voltages button)
   lets user enter external meter readings for input, output, and battery voltage.
   Shows UPS vs meter delta.

7. **DONE -- Battery packs editing:** Number of external battery packs (> command)
   added as editable CAUTION-tier setting. Affects runtime calculation.

8. **DONE -- Battery age warning:** Battery age computed from `battery_replace_date`.
   Yellow warning banner in main tab when batteries exceed 2 years.
