"""Decode hex register values into individual bit flags."""

from apc_ups.protocol.constants import (
    STATUS_BITS, STATE_BITS, TRIP1_BITS, TRIP_BITS,
)


def decode_hex_register(hex_str: str, bit_map: dict[int, str]) -> dict[str, bool]:
    """Decode a 2-character hex string into a dict of {label: is_set}.

    Args:
        hex_str: Two hex characters (e.g. "08").
        bit_map: Mapping of bit number (0-7) to label string.

    Returns:
        Dict of {label: bool} for each bit in the map.
    """
    try:
        value = int(hex_str, 16)
    except (ValueError, TypeError):
        return {label: False for label in bit_map.values()}

    result = {}
    for bit_num, label in sorted(bit_map.items(), reverse=True):
        result[label] = bool(value & (1 << bit_num))
    return result


def decode_status(hex_str: str) -> dict[str, bool]:
    """Decode UPS Status register (Q command)."""
    return decode_hex_register(hex_str, STATUS_BITS)


def decode_state(hex_str: str) -> dict[str, bool]:
    """Decode State register (~ command)."""
    return decode_hex_register(hex_str, STATE_BITS)


def decode_trip1(hex_str: str) -> dict[str, bool]:
    """Decode Trip1 register (' command)."""
    return decode_hex_register(hex_str, TRIP1_BITS)


def decode_trip(hex_str: str) -> dict[str, bool]:
    """Decode Trip register (8 command)."""
    return decode_hex_register(hex_str, TRIP_BITS)
