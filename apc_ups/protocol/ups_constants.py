"""Factory default smart constants for known APC UPS models.

Data sourced from the kirbah/apc-ups community reference:
https://github.com/kirbah/apc-ups/blob/master/docs/UPS-constants.md

Smart constants (registers 0, 4, 5, 6) are battery discharge curve
parameters stored in EEPROM. They are factory-set per model and
normally should not be modified. Comparing current values to factory
defaults can reveal if calibration or EEPROM corruption has altered them.
"""

import re

SOURCE_URL = "https://github.com/kirbah/apc-ups/blob/master/docs/UPS-constants.md"

# Each entry: (model, reg_4, reg_5, reg_6, reg_0, firmware, battery_voltage)
# Values are hex strings as documented. Empty string = not available.
_MODEL_DATA = [
    ("SU250",               "",   "EE", "F8", "B1", "",        ""),
    ("SU400",               "",   "EE", "F8", "9F", "",        ""),
    ("SU420",               "25", "95", "09", "",   "21.1.I",  "24v"),
    ("SU420I",              "25", "95", "09", "85", "21.7.I",  ""),
    ("SU420SI",             "0E", "95", "0A", "8C", "",        ""),
    ("SU450,700",           "28", "F2", "FA", "96", "52.11.I", "24v"),
    ("SU450XL,700XL",       "28", "EE", "F8", "9F", "51.9.I",  "24v"),
    ("SU600",               "",   "EA", "F4", "9F", "",        ""),
    ("SU620I",              "29", "99", "0B", "8A", "",        ""),
    ("SU620 (2001year)",    "10", "97", "0B", "99", "22.6.I",  ""),
    ("SU700RMI2U",          "07", "B1", "0D", "92", "152.4.I", ""),
    ("SU900",               "",   "F3", "FC", "9F", "",        ""),
    ("SU1000RMI2U",         "08", "B5", "0D", "C7", "157.3.I", ""),
    ("SU1250",              "",   "EE", "FA", "9F", "",        ""),
    ("SU2000",              "",   "F1", "F9", "9F", "",        ""),
    ("SU1000,INET",         "35", "EF", "F9", "A0", "60.11.I", ""),
    ("SU1000XL",            "17", "EE", "F9", "D5", "",        ""),
    ("SU1000XL",            "34", "EE", "FC", "9A", "61.9.I",  ""),
    ("SU1400",              "35", "EE", "FC", "9A", "70.11.I", ""),
    ("SU1400RM",            "28", "ED", "FA", "89", "",        ""),
    ("SU1400RMI2U",         "08", "B4", "10", "A3", "162.3.I", ""),
    ("SU1400R2IBX135",      "08", "B4", "10", "A3", "",        ""),
    ("SU1400RMXLI3U",       "45", "F6", "F4", "80", "73.x.I",  ""),
    ("SU1400RMXLI3U",       "20", "F3", "FD", "81", "73.x.I",  ""),
    ("SU1400XL,XLI,RM",    "45", "F6", "E4", "80", "",        ""),
    ("SU2200I",             "35", "EE", "FB", "AF", "90.14.I", "48v"),
    ("SU2200XL,3000",       "35", "EE", "FB", "AF", "90.14.I", "48v"),
    ("SU3000NET",           "",   "",   "",   "96", "",        "48v"),
    ("SU3000RMXLI3Ublk",    "35", "F3", "F4", "AF", "93.14.I", "48v"),
    ("SU5000I white",       "20", "F2", "FA", "91", "110.14.I",""),
    ("BP420SI",             "0E", "95", "0A", "8C", "11.2.I",  ""),
    ("BP500AVR",            "",   "",   "",   "",   "17.1.I",  ""),
    ("BP650SI",             "10", "97", "0C", "91", "12.3.I",  ""),
    ("Power Stack 250",     "0C", "95", "0F", "B2", "26.5.I",  ""),
    ("Power Stack 450",     "0D", "96", "10", "99", "26.5.I",  ""),
    ("SC250RMI1U",          "0C", "95", "0F", "B3", "735.a.1", ""),
    ("SC420I",              "0E", "95", "0A", "8C", "725.1.I", ""),
    ("SC620I",              "10", "97", "0B", "99", "726.x.I", ""),
    ("SC1000I",             "08", "95", "10", "94", "737.x.I", ""),
    ("SC1500I",             "07", "95", "14", "8F", "738.x.I", ""),
    ("MATRIX 3000,5000",    "",   "E9", "F5", "B0", "",        ""),
    ("SUA750XLI",           "0A", "B9", "0C", "86", "630.3.I", ""),
    ("SUA750I",             "04", "B6", "14", "82", "651.12.I",""),
    ("SUA750RMI2U",         "07", "B1", "0D", "82", "619.12.I",""),
    ("SUA1000I",            "07", "B5", "13", "BC", "652.12.I","24v"),
    ("SUA1000XLI",          "0B", "BD", "0F", "7F", "681.13.I",""),
    ("SUA1500I",            "09", "B9", "13", "A1", "601/653.x.I", "24v"),
    ("SUA1500RMI2U",        "08", "B4", "10", "A1", "617.3.I", ""),
    ("SUA2200I",            "08", "B8", "12", "B3", "654.12.I",""),
    ("SUA2200RMI2U",        "09", "BC", "11", "81", "665.4.I", ""),
    ("SUA2200XLI",          "0A", "B7", "0F", "7F", "690.x.I", ""),
    ("SUA3000RMI2U",        "04", "B9", "0E", "70", "666.4.I", ""),
    ("SUA3000RMXLI3U",      "0A", "B6", "0E", "89", "",        ""),
    ("SUOL1000I",           "06", "B6", "1B", "A6", "",        ""),
    ("SUOL2000XL",          "0D", "BD", "14", "75", "416.5.I", ""),
    ("SURT1000XLI",         "0A", "BB", "19", "A8", "411.x.I", ""),
    ("SURT3000XLI",         "06", "B6", "0F", "CA", "450.2.I", ""),
    ("SURT5000XLI",         "05", "BA", "15", "86", "451.13.W",""),
    ("SURT6000XLI",         "07", "BE", "24", "7E", "",        ""),
    ("SURT7500XLI",         "03", "BB", "20", "97", "",        ""),
    ("SURT8000XLI",         "0A", "C0", "28", "8F", "",        ""),
    ("SURT10000XLI",        "06", "B8", "19", "7E", "476.12.W",""),
    ("SURTA1500XL",         "05", "B7", "12", "A0", "",        ""),
    ("SURTA1500XLJ",        "05", "B7", "12", "A0", "",        ""),
    ("SURTA2000XL",         "04", "BC", "19", "7E", "",        ""),
    ("SURTA2400XLJ",        "0C", "B5", "10", "E4", "",        ""),
    ("SURTA3000XL",         "0C", "BD", "1F", "C2", "",        ""),
    ("SUM1500RMXLI2U",      "03", "B7", "0D", "A5", "716.3.I", ""),
    ("SUM3000RMXLI2U",      "03", "B7", "0D", "A5", "715.3.I", ""),
]


def hex_to_ups_decimal(hex_val: str) -> str:
    """Convert a hex string to the 3-digit decimal string the UPS reports.

    The UPS protocol returns smart constants as 3-digit zero-padded decimal
    strings (e.g., "025", "175"). The reference table stores them in hex.

    >>> hex_to_ups_decimal("AF")
    '175'
    >>> hex_to_ups_decimal("35")
    '053'
    >>> hex_to_ups_decimal("")
    ''
    """
    if not hex_val:
        return ""
    try:
        return f"{int(hex_val, 16):03d}"
    except ValueError:
        return ""


def get_factory_defaults(model_entry: tuple) -> dict:
    """Return factory defaults as a dict with decimal string values.

    Keys: 'reg_0', 'reg_4', 'reg_5', 'reg_6', 'model', 'firmware', 'battery_voltage'.
    Register values are converted from hex to 3-digit decimal.
    """
    model, reg_4, reg_5, reg_6, reg_0, firmware, batt_v = model_entry
    return {
        "model": model,
        "reg_0": hex_to_ups_decimal(reg_0),
        "reg_4": hex_to_ups_decimal(reg_4),
        "reg_5": hex_to_ups_decimal(reg_5),
        "reg_6": hex_to_ups_decimal(reg_6),
        "reg_0_hex": reg_0,
        "reg_4_hex": reg_4,
        "reg_5_hex": reg_5,
        "reg_6_hex": reg_6,
        "firmware": firmware,
        "battery_voltage": batt_v,
    }


def lookup_model(model_name: str) -> list[tuple]:
    """Find matching reference entries for a UPS model name.

    Matches based on the numeric model number (e.g., "2200") and
    relevant suffixes (XL, RM, I).

    Returns a list of matching entries from _MODEL_DATA, best match first.
    """
    if not model_name:
        return []

    name_upper = model_name.upper().replace("-", "").replace(" ", "")

    # Extract 3-4 digit model numbers from the UPS model string
    numbers = re.findall(r"\d{3,5}", model_name)
    if not numbers:
        return []

    has_xl = "XL" in name_upper
    has_rm = "RM" in name_upper

    scored = []
    for entry in _MODEL_DATA:
        ref_name = entry[0]
        ref_upper = ref_name.upper().replace("-", "").replace(" ", "")

        # Must share at least one numeric model number
        score = 0
        for num in numbers:
            if num in ref_upper:
                score += 10
                break

        if score == 0:
            continue

        # Suffix matching
        ref_has_xl = "XL" in ref_upper
        ref_has_rm = "RM" in ref_upper

        if has_xl and ref_has_xl:
            score += 5
        elif not has_xl and not ref_has_xl:
            score += 2
        elif has_xl != ref_has_xl:
            score -= 2

        if has_rm and ref_has_rm:
            score += 3
        elif not has_rm and not ref_has_rm:
            score += 1

        scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [entry for _, entry in scored]
