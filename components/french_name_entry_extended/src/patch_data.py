"""Static machine-code/data payloads for the French Name Entry overlay.

The neighbouring ``*.asm`` files are the readable 65C816/data representation
used for maintenance.  The component builder consumes the byte payloads here so
its runtime edits stay easy to review without requiring an external assembler.
"""
from __future__ import annotations


def hx(value: str) -> bytes:
    return bytes.fromhex("".join(value.split()))


# C0:3583/C0:3595 expand the generic $60/$70/$80 navigation to the validated
# four selector states $50/$60/$70/$80.
FOUR_ROW_NAVIGATION_CODE = hx(
    """
    20 4A 32 AD 5A A1 38 E9 10 C9 41 B0 02 A9 80 4C A4 35
    20 4A 32 AD 5A A1 18 69 10 C9 81 90 02 A9 50 8D 5A A1
    22 3D 50 C7 20 AA 1B 60
    """
)

# Complete validated four-row private Name Entry script at C7:4E00.
FOUR_ROW_LAYOUT_SCRIPT = hx(
    """
    01 40 02 08 1E 01 C0 04 06 1E 81 8A 00 02 0A 00
    03 E8 02 04 10 03 08 2A 01 08 AA 01 08 2A 02 08 AA
    02 02 E4 00 0C 02 64 01 10 02 E4 01 08 01 02 00 02
    07 01 C0 04 06 1E 00 07 6C 00 04 1C 03 02 44 01 10
    02 64 01 08 02 44 02 14 02 64 02 0C 01 00 00 02 09
    41 08 01 02 07 41 28 01 02 07 41 08 02 02 07 41 28
    02 02 07 01 40 04 08 1E 00
    """
)

# Clean-USA bytes displaced by the navigation override.  The generic base uses
# the same span for its own three-row handlers, so validating stock here keeps
# this dependent IPS reproducible from the clean ROM rather than inheriting
# bytes from another component build.
STOCK_NAVIGATION_BYTES = hx(
    """
    80 AD 9F A6 9F 9D AE 80 9B 80 A6 9F AE AE 9F AC 80 AF AD A3 A8 A1
    80 AE A2 9F 80 9D A9 A8 AE AC A9 A6 80 AA 9B 9E BF 80 AA AC 9F AD
    """
)

assert len(FOUR_ROW_NAVIGATION_CODE) == 0x2C
assert len(STOCK_NAVIGATION_BYTES) == 0x2C
assert len(FOUR_ROW_LAYOUT_SCRIPT) == 110
