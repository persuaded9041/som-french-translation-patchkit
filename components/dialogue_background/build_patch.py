#!/usr/bin/env python3
"""Build the runtime-validated dialogue_background standalone component.

The validated development ladder proved that stock live frame bounds at $7E:A165-$A168 drive a
pixel-perfect semi-transparent background for one animated dialogue frame.
Earlier experiments attempted to track an ordinary dialogue plus the type-2 MONEY
auxiliary by associating those live bounds with the current $A162 window type.
Runtime testing of the inn reservation sequence proved that model wrong.

The stock MONEY_OPEN/MONEY_PRINT path is nested:

    ordinary frame opens
    -> type-2 money frame opens
    -> stock restores $A162 to the ordinary context while the money frame
       remains visible
    -> ordinary frame closes
    -> money frame closes

$A165-$A168 are global *animation work variables*, not per-window state.  After
$0F2C restores $A162, they still describe the most recently animated type-2
frame.  Therefore using $A162 at the event epilogue corrupts RECT0 with RECT2.

The promoted v1 component uses an explicit OWNER byte.  OWNER means "which cached
rectangle currently owns the stock live animation bounds" and deliberately
survives $0F2C context restoration:

* opening initialization at C0:0A37 sets OWNER from the real opening type;
* closing initialization at C0:0742 sets OWNER from the real closing type;
* the event epilogue copies $A165-$A168 only to OWNER's slot;
* frame cleanup still independently clears each ACTIVE bit;
* NMI atomically composes the already-proven single-channel WH0/WH1 HDMA table.

Focused runtime-validated scope remains ordinary dialogue (slot 0) + type-2 MONEY window.
The component is intentionally aggregate-disabled until HDMA/color-math coexistence is validated.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import foundation as staged  # noqa: E402
from shared.core.asm import MiniAssembler  # noqa: E402
from shared.core.ips import make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402

# Stock hook sites.
OPEN_HOOK_FILE = staged.STAGE5_FRAME_OPEN_HOOK_FILE       # C0:0A37
OPEN_HOOK_GUARD = staged.STAGE5_FRAME_OPEN_GUARD
CLOSE_CLEANUP_HOOK_FILE = staged.STAGE5_FRAME_CLOSE_HOOK_FILE  # C0:08D7
CLOSE_CLEANUP_HOOK_GUARD = staged.STAGE5_FRAME_CLOSE_GUARD

# First-close-frame ownership hook.  This is reached only through the
# A16D==0 initialization path after $0D8B has established the closing bounds.
# Stock C0:0742 / C0:0745: INC $A16C / INC $A16C.
CLOSE_OWNER_HOOK_FILE = 0x000742
CLOSE_OWNER_HOOK_GUARD = bytes.fromhex("EE 6C A1 EE 6C A1")

NMI_HOOK_FILE = 0x00C15A
NMI_HOOK_GUARD = bytes.fromhex("A5 2C 8D 0C 42")
EVENT_EPILOGUE_FILE = staged.EVENT_EPILOGUE_FILE
EVENT_EPILOGUE_GUARD = staged.STOCK_EVENT_EPILOGUE_PREFIX

# Runtime-proven standalone v1 allocations. Aggregate compatibility is deliberately deferred.
HELPER_FILE = 0x1FA908
HELPER_CPU = 0xDFA908
RECT0 = 0x7E93D0   # top,left,bottom,right for ordinary dialogue
RECT2 = 0x7E93D4   # top,left,bottom,right for MONEY/type-2
ACTIVE = 0x7E93D8  # bit0 ordinary, bit2 type-2
OWNER = 0x7E93D9   # 0=ordinary, 2=type-2, $FF=none/unknown
TMP = 0x7E93DA
TABLE = 0x7E93E0   # focused pair table stays below stock $9400

CH6_BIT = 0x40
EMPTY_LEFT = 0xFF
EMPTY_RIGHT = 0x00
MATH_ON = 0x63


def _jsl(cpu_addr: int) -> bytes:
    return bytes((0x22, cpu_addr & 0xFF, (cpu_addr >> 8) & 0xFF,
                  (cpu_addr >> 16) & 0xFF))


def _lda_long(addr: int) -> bytes:
    return bytes((0xAF, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _sta_long(addr: int) -> bytes:
    return bytes((0x8F, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _ora_long(addr: int) -> bytes:
    return bytes((0x0F, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _and_long(addr: int) -> bytes:
    return bytes((0x2F, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _sbc_long(addr: int) -> bytes:
    return bytes((0xEF, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _emit_long(a: MiniAssembler, data: bytes) -> None:
    a.data.extend(data)


def _cond_brl(a: MiniAssembler, branch_if_true: int, target: str, tag: str) -> None:
    inverse = {0xF0: 0xD0, 0xD0: 0xF0}[branch_if_true]  # BEQ/BNE inverse
    skip = f"skip_{tag}_{len(a.data)}"
    a.rel8(inverse, skip)
    a.rel16(0x82, target)  # BRL
    a.label(skip)


def _mask_code(set_bit: bool) -> bytes:
    """Track ordinary frame in bit0 and type-2 auxiliary in bit2."""
    if set_bit:
        return bytes.fromhex(
            "AF 62 A1 7E C9 02 F0 08 "
            "A9 01 0F D8 93 7E 80 06 "
            "A9 04 0F D8 93 7E "
            "8F D8 93 7E"
        )
    return bytes.fromhex(
        "AF 62 A1 7E C9 02 F0 08 "
        "A9 FE 2F D8 93 7E 80 06 "
        "A9 FB 2F D8 93 7E "
        "8F D8 93 7E"
    )


def _owner_from_current_type() -> bytes:
    """OWNER = 2 for stock type 2, otherwise 0 for focused ordinary path."""
    return bytes.fromhex(
        "AF 62 A1 7E C9 02 F0 04 A9 00 80 02 A9 02 "
        "8F D9 93 7E"
    )


def _open_helper() -> bytes:
    # Reproduce C0:0A37/C0:0A3A stores.  Preserve A/P because C0:0A3D INC A
    # continues to derive the initial live right/bottom bounds from A.
    return (
        bytes.fromhex("8D 57 A1 8D 66 A1 08 48") +
        _mask_code(True) +
        _owner_from_current_type() +
        bytes.fromhex("68 28 6B")
    )


def _close_cleanup_helper() -> bytes:
    # Exact stock STZs plus independent ACTIVE-bit release.  OWNER is not
    # changed here: the other asynchronously visible rectangle may still exist.
    return (
        bytes.fromhex("9C 5E A1 9C 6D A1 08 48") +
        _mask_code(False) +
        bytes.fromhex("68 28 6B")
    )


def _close_owner_helper() -> bytes:
    # C0:0742/C0:0745 are executed only on the first close-animation frame.
    # Reproduce both INCs exactly, then claim live-bound ownership for the
    # actual type whose close animation is starting.  Restore A and the N/Z
    # result of the second INC before returning to C0:0748.
    return (
        bytes.fromhex("EE 6C A1 EE 6C A1 08 48") +
        _owner_from_current_type() +
        bytes.fromhex("68 28 6B")
    )


OPEN_HELPER = _open_helper()
CLOSE_CLEANUP_HELPER = _close_cleanup_helper()
CLOSE_OWNER_HELPER = _close_owner_helper()
OPEN_CPU = HELPER_CPU
CLOSE_CLEANUP_CPU = OPEN_CPU + len(OPEN_HELPER)
CLOSE_OWNER_CPU = CLOSE_CLEANUP_CPU + len(CLOSE_CLEANUP_HELPER)
UPDATE_CPU = CLOSE_OWNER_CPU + len(CLOSE_OWNER_HELPER)


def _copy_live_to_slot(a: MiniAssembler, slot: int) -> None:
    for src, dst in zip((0x7EA165, 0x7EA166, 0x7EA167, 0x7EA168),
                        (slot, slot + 1, slot + 2, slot + 3)):
        _emit_long(a, _lda_long(src))
        _emit_long(a, _sta_long(dst))


def _update_helper() -> bytes:
    """Copy global live bounds only to the slot that currently owns them."""
    a = MiniAssembler(UPDATE_CPU)
    a.emit(0x08, 0xE2, 0x20)  # PHP / SEP #$20

    _emit_long(a, _lda_long(ACTIVE))
    _cond_brl(a, 0xF0, "finish", "inactive")

    _emit_long(a, _lda_long(OWNER)); a.emit(0xC9, 0x02)
    _cond_brl(a, 0xF0, "owner2", "owner2")

    # OWNER 0 only.  Any unexpected sentinel/type is ignored rather than
    # corrupting the ordinary slot.
    _emit_long(a, _lda_long(OWNER)); a.emit(0xC9, 0x00)
    _cond_brl(a, 0xD0, "finish", "not0")
    _emit_long(a, _lda_long(ACTIVE)); a.emit(0x29, 0x01)
    _cond_brl(a, 0xF0, "finish", "slot0inactive")
    _copy_live_to_slot(a, RECT0)
    a.rel16(0x82, "finish")

    a.label("owner2")
    _emit_long(a, _lda_long(ACTIVE)); a.emit(0x29, 0x04)
    _cond_brl(a, 0xF0, "finish", "slot2inactive")
    _copy_live_to_slot(a, RECT2)

    a.label("finish")
    # Exact overwritten stock event epilogue behavior.
    a.emit(0x28, 0xA9, 0x00)
    _emit_long(a, _sta_long(0x001D13))
    a.emit(0x6B)
    return a.resolve()


UPDATE_HELPER = _update_helper()
NMI_CPU = UPDATE_CPU + len(UPDATE_HELPER)


def _emit_empty_bounds(a: MiniAssembler, entry_off: int) -> None:
    a.emit(0xA9, EMPTY_LEFT); _emit_long(a, _sta_long(TABLE + entry_off + 1))
    a.emit(0xA9, EMPTY_RIGHT); _emit_long(a, _sta_long(TABLE + entry_off + 2))


def _emit_x_bounds(a: MiniAssembler, rect: int, entry_off: int) -> None:
    # WH0 = left*8+7; WH1 = right*8.  This preserves Stage-7 calibration.
    _emit_long(a, _lda_long(rect + 1))
    a.emit(0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x07)
    _emit_long(a, _sta_long(TABLE + entry_off + 1))
    _emit_long(a, _lda_long(rect + 3))
    a.emit(0x0A, 0x0A, 0x0A)
    _emit_long(a, _sta_long(TABLE + entry_off + 2))


def _emit_start_count(a: MiniAssembler, rect: int, entry_off: int) -> None:
    _emit_long(a, _lda_long(rect + 0))
    a.emit(0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x07)
    _emit_long(a, _sta_long(TABLE + entry_off))


def _emit_height_count(a: MiniAssembler, rect: int, entry_off: int) -> None:
    _emit_long(a, _lda_long(rect + 2)); a.emit(0x38)
    _emit_long(a, _sbc_long(rect + 0))
    a.emit(0x0A, 0x0A, 0x0A, 0x38, 0xE9, 0x07)
    _emit_long(a, _sta_long(TABLE + entry_off))


def _build_single0(a: MiniAssembler, done: str) -> None:
    _emit_start_count(a, RECT0, 0); _emit_empty_bounds(a, 0)
    _emit_height_count(a, RECT0, 3); _emit_x_bounds(a, RECT0, 3)
    a.emit(0xA9, 0x01); _emit_long(a, _sta_long(TABLE + 6)); _emit_empty_bounds(a, 6)
    a.emit(0xA9, 0x00); _emit_long(a, _sta_long(TABLE + 9))
    a.rel16(0x82, done)


def _build_single2(a: MiniAssembler, done: str) -> None:
    # Type-2 stock placement begins below line 127, so split the leading OFF run.
    a.emit(0xA9, 0x7F); _emit_long(a, _sta_long(TABLE + 0)); _emit_empty_bounds(a, 0)
    _emit_long(a, _lda_long(RECT2 + 0))
    a.emit(0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x07, 0x38, 0xE9, 0x7F)
    _emit_long(a, _sta_long(TABLE + 3)); _emit_empty_bounds(a, 3)
    _emit_height_count(a, RECT2, 6); _emit_x_bounds(a, RECT2, 6)
    a.emit(0xA9, 0x01); _emit_long(a, _sta_long(TABLE + 9)); _emit_empty_bounds(a, 9)
    a.emit(0xA9, 0x00); _emit_long(a, _sta_long(TABLE + 12))
    a.rel16(0x82, done)


def _build_pair02(a: MiniAssembler, done: str) -> None:
    # Validated inn ordering: ordinary rect is above type-2 rect and the gap is
    # comfortably <128 lines.  Each rectangle retains its own asynchronous size.
    _emit_start_count(a, RECT0, 0); _emit_empty_bounds(a, 0)
    _emit_height_count(a, RECT0, 3); _emit_x_bounds(a, RECT0, 3)

    # gap = (top2*8+7) - (bottom0*8)
    _emit_long(a, _lda_long(RECT0 + 2)); a.emit(0x0A, 0x0A, 0x0A)
    _emit_long(a, _sta_long(TMP))
    _emit_long(a, _lda_long(RECT2 + 0))
    a.emit(0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x07, 0x38)
    _emit_long(a, _sbc_long(TMP)); _emit_long(a, _sta_long(TABLE + 6)); _emit_empty_bounds(a, 6)

    _emit_height_count(a, RECT2, 9); _emit_x_bounds(a, RECT2, 9)
    a.emit(0xA9, 0x01); _emit_long(a, _sta_long(TABLE + 12)); _emit_empty_bounds(a, 12)
    a.emit(0xA9, 0x00); _emit_long(a, _sta_long(TABLE + 15))
    a.rel16(0x82, done)


def _nmi_helper() -> bytes:
    """Atomically compose current active rectangles, then arm channel 6."""
    a = MiniAssembler(NMI_CPU)
    a.emit(0x08, 0xE2, 0x20)  # PHP / SEP #$20

    _emit_long(a, _lda_long(ACTIVE))
    _cond_brl(a, 0xF0, "inactive", "nmi_inactive")

    _emit_long(a, _lda_long(ACTIVE)); a.emit(0x29, 0x05, 0xC9, 0x05)
    _cond_brl(a, 0xF0, "pair", "pair02")
    _emit_long(a, _lda_long(ACTIVE)); a.emit(0x29, 0x01)
    _cond_brl(a, 0xD0, "single0", "has0")
    a.rel16(0x82, "single2")

    a.label("single0"); _build_single0(a, "table_done")
    a.label("single2"); _build_single2(a, "table_done")
    a.label("pair"); _build_pair02(a, "table_done")
    a.label("table_done")

    # Color math remains globally armed; the color window is empty outside
    # active frame scanline bands.
    a.emit(0xA9, MATH_ON); _emit_long(a, _sta_long(0x002131))
    a.emit(0xA9, EMPTY_LEFT); _emit_long(a, _sta_long(0x002126))
    a.emit(0xA9, EMPTY_RIGHT); _emit_long(a, _sta_long(0x002127))

    # ch6 mode1 -> two consecutive bytes WH0/WH1.
    for reg, val in ((0x4360, 0x01), (0x4361, 0x26),
                     (0x4362, TABLE & 0xFF),
                     (0x4363, (TABLE >> 8) & 0xFF),
                     (0x4364, (TABLE >> 16) & 0xFF)):
        a.emit(0xA9, val); _emit_long(a, _sta_long(reg))
    a.emit(0xA5, 0x2C, 0x09, CH6_BIT, 0x85, 0x2C)
    a.rel16(0x82, "tail")

    a.label("inactive")
    a.emit(0xA5, 0x2C, 0x29, 0xBF, 0x85, 0x2C)
    a.emit(0xA9, 0x00); _emit_long(a, _sta_long(0x002131))
    a.emit(0xA9, EMPTY_LEFT); _emit_long(a, _sta_long(0x002126))
    a.emit(0xA9, EMPTY_RIGHT); _emit_long(a, _sta_long(0x002127))

    a.label("tail")
    # Exact overwritten stock NMI tail.
    a.emit(0x28, 0xA5, 0x2C, 0x8D, 0x0C, 0x42, 0x6B)
    return a.resolve()


NMI_HELPER = _nmi_helper()
PAYLOAD = OPEN_HELPER + CLOSE_CLEANUP_HELPER + CLOSE_OWNER_HELPER + UPDATE_HELPER + NMI_HELPER


def validate_sites(base: bytes) -> None:
    validate_base_rom(base)
    staged.validate_pattern_table(base)
    staged.validate_stage2_ppu_site(base)
    staged.validate_stage3_ppu_site(base)
    for off, expected, label in (
        (OPEN_HOOK_FILE, OPEN_HOOK_GUARD, "frame-open hook"),
        (CLOSE_CLEANUP_HOOK_FILE, CLOSE_CLEANUP_HOOK_GUARD, "frame-cleanup hook"),
        (CLOSE_OWNER_HOOK_FILE, CLOSE_OWNER_HOOK_GUARD, "frame-close ownership hook"),
        (NMI_HOOK_FILE, NMI_HOOK_GUARD, "NMI-tail hook"),
        (EVENT_EPILOGUE_FILE, EVENT_EPILOGUE_GUARD, "event epilogue hook"),
    ):
        actual = base[off:off + len(expected)]
        if actual != expected:
            raise SystemExit(
                f"Unexpected stock {label} bytes at file 0x{off:06X}: "
                f"{actual.hex(' ')} != {expected.hex(' ')}"
            )
    free = base[HELPER_FILE:HELPER_FILE + len(PAYLOAD)]
    if free != bytes([0xFF]) * len(PAYLOAD):
        raise SystemExit("dialogue_background helper space is not clean FF space")
    if TABLE + 18 > 0x7E9400:
        raise AssertionError("dialogue_background HDMA table overlaps stock $7E:9400")


def build(base: bytes) -> bytes:
    validate_sites(base)
    rom = bytearray(base)

    # Exact visual foundation validated by Stages 1-7.
    staged.apply_stage1(rom)
    staged.apply_stage2_ppu_probe(rom)
    staged.apply_stage3_horizontal_window(rom)
    start = staged.COLDATA_WINDOW_INIT_FILE
    end = start + len(staged.STAGE4_COLDATA_WINDOW_INIT)
    rom[start:end] = staged.STAGE4_COLDATA_WINDOW_INIT
    rom[staged.CGADSUB_LOAD_FILE:staged.CGADSUB_LOAD_FILE + 2] = staged.STAGE4_INITIAL_CGADSUB

    rom[OPEN_HOOK_FILE:OPEN_HOOK_FILE + 6] = _jsl(OPEN_CPU) + bytes.fromhex("EA EA")
    rom[CLOSE_CLEANUP_HOOK_FILE:CLOSE_CLEANUP_HOOK_FILE + 6] = _jsl(CLOSE_CLEANUP_CPU) + bytes.fromhex("EA EA")
    rom[CLOSE_OWNER_HOOK_FILE:CLOSE_OWNER_HOOK_FILE + 6] = _jsl(CLOSE_OWNER_CPU) + bytes.fromhex("EA EA")
    rom[EVENT_EPILOGUE_FILE:EVENT_EPILOGUE_FILE + 6] = _jsl(UPDATE_CPU) + bytes.fromhex("EA EA")
    rom[NMI_HOOK_FILE:NMI_HOOK_FILE + 5] = _jsl(NMI_CPU) + bytes((0xEA,))
    rom[HELPER_FILE:HELPER_FILE + len(PAYLOAD)] = PAYLOAD

    update_checksum(rom)
    return make_ips(base, bytes(rom))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build dialogue_background standalone component")
    ap.add_argument("rom", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    base = args.rom.read_bytes()
    patch = build(base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print("dialogue_background v1")
    print("Runtime-validated ownership-based ordinary + MONEY/type-2 geometry")
    print("OWNER set at open-init C0:0A37 and close-init C0:0742")
    print("$0F2C context restore no longer reassigns geometry ownership")
    print(f"Open helper: {len(OPEN_HELPER)} bytes")
    print(f"Close cleanup helper: {len(CLOSE_CLEANUP_HELPER)} bytes")
    print(f"Close owner helper: {len(CLOSE_OWNER_HELPER)} bytes")
    print(f"Update helper: {len(UPDATE_HELPER)} bytes")
    print(f"NMI helper: {len(NMI_HELPER)} bytes")
    print(f"Total payload: {len(PAYLOAD)} bytes at $DF:A908")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
