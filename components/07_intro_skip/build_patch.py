#!/usr/bin/env python3
"""Build the runtime-validated non-blocking 2-second R-hold intro skip."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.ips import make_ips  # noqa: E402
from shared.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.asm65816 import MiniAssembler, lo24  # noqa: E402

EVENT_HOOK_FILE = 0x00012C
EVENT_HOOK_STOCK = bytes.fromhex("08 E2 20 C2")
EVENT_HOOK_PATCH = bytes.fromhex("5C 00 74 ED")  # JML $ED7400

NMI_RELEASE_HOOK_FILE = 0x0000AC34
NMI_RELEASE_HOOK_STOCK = bytes.fromhex("AD 0E 00 2D")  # LDA $000E / first byte of AND $000F
NMI_RELEASE_HOOK_PATCH = bytes.fromhex("5C 90 74 ED")  # JML $ED7490

SKIP_SCRIPT_FILE = 0x0AFFC0
HELPER_FILE = 0x2D7400
HELPER_RESERVED_END = 0x2D74FF
NMI_HELPER_FILE = 0x2D7490
INTRO_START = 0x0C02
INTRO_END = 0x0E8B
HOLD_FRAMES = 0x78
HOLD_START_WRAM = 0x7E938A
HOLD_ACTIVE_WRAM = 0x7E938B

SKIP_SCRIPT = bytes.fromhex("51 18 00 2A F8 11 06 00")



def build_helper() -> bytes:
    a = MiniAssembler(0xED7400)

    # Reproduce the stock prologue overwritten at C0:012C.
    a.emit(0x08)                    # PHP
    a.emit(0xE2, 0x20)              # SEP #$20 (8-bit A)
    a.emit(0xC2, 0x10)              # REP #$10 (16-bit X/Y)

    # Component 07 is active only in translated intro event bank $CA.
    a.emit(0xAF, *lo24(0x001D03))   # LDA.l $001D03
    a.emit(0xC9, 0xCA)              # CMP #$CA
    a.rel8(0xD0, "done8")           # BNE

    a.emit(0xC2, 0x20)              # REP #$20
    a.emit(0xAF, *lo24(0x001D01))   # LDA.l $001D01

    # Deterministic initialization at the first byte of event $0400.
    a.emit(0xC9, INTRO_START & 0xFF, INTRO_START >> 8)
    a.rel8(0xD0, "range_check")     # BNE
    a.emit(0xE2, 0x20)              # SEP #$20
    a.emit(0xA9, 0x00)              # LDA #$00
    a.emit(0x8F, *lo24(HOLD_ACTIVE_WRAM))
    a.emit(0x8F, *lo24(HOLD_START_WRAM))
    a.emit(0xC2, 0x20)              # REP #$20
    a.emit(0xAF, *lo24(0x001D01))   # reload pointer

    a.label("range_check")
    a.emit(0xC9, INTRO_START & 0xFF, INTRO_START >> 8)
    a.rel8(0x90, "done16")          # BCC
    a.emit(0xC9, INTRO_END & 0xFF, INTRO_END >> 8)
    a.rel8(0xB0, "done16")          # BCS

    a.emit(0xE2, 0x20)              # SEP #$20
    a.emit(0xAF, *lo24(0x004218))   # LDA.l $4218
    a.emit(0x29, 0x10)              # AND #$10 (runtime-validated R)
    a.rel8(0xF0, "released")        # BEQ

    # First observed held frame: remember stock NMI frame counter and return.
    a.emit(0xAF, *lo24(HOLD_ACTIVE_WRAM))
    a.rel8(0xD0, "holding")         # BNE
    a.emit(0xAF, *lo24(0x0000F4))   # LDA.l $00F4
    a.emit(0x8F, *lo24(HOLD_START_WRAM))
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(HOLD_ACTIVE_WRAM))
    a.rel8(0x80, "done8")           # BRA

    # Subsequent calls are non-blocking: compare elapsed modulo-256 frames.
    a.label("holding")
    a.emit(0xAF, *lo24(0x0000F4))   # LDA.l $00F4
    a.emit(0x38)                     # SEC
    a.emit(0xEF, *lo24(HOLD_START_WRAM))  # SBC.l $7E938A
    a.emit(0xC9, HOLD_FRAMES)        # CMP #$78
    a.rel8(0x90, "done8")           # BCC

    # Threshold reached: disarm local state, then use the runtime-validated
    # Runtime-validated event-pointer redirect.
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(HOLD_ACTIVE_WRAM))
    a.emit(0xC2, 0x20)              # REP #$20
    a.emit(0xA9, 0xC0, 0xFF)        # LDA #$FFC0
    a.emit(0x8F, *lo24(0x001D01))
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0xCA)
    a.emit(0x8F, *lo24(0x001D03))
    a.rel8(0x80, "done8")           # BRA

    # Any release before the threshold cancels the hold completely.
    a.label("released")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(HOLD_ACTIVE_WRAM))
    a.rel8(0x80, "done8")

    a.label("done16")
    a.emit(0xE2, 0x20)              # SEP #$20
    a.label("done8")
    a.emit(0x5C, 0x31, 0x01, 0xC0)  # JML $C00131
    return a.resolve()


INPUT_HELPER = build_helper()


def build_nmi_release_helper() -> bytes:
    """Clear an active R hold on any NMI that observes R released.

    This is deliberately tiny and non-blocking. It restores the stock
    instructions overwritten at C0:AC34 before returning to C0:AC3A.
    """
    a = MiniAssembler(0xED7490)

    # NMI is already in 8-bit A at this point. Do not touch X/Y.
    a.emit(0xAF, *lo24(HOLD_ACTIVE_WRAM))  # LDA.l $7E938B
    a.rel8(0xF0, "stock")                  # BEQ
    a.emit(0xAF, *lo24(0x004218))           # LDA.l $4218
    a.emit(0x29, 0x10)                      # AND #$10 (runtime-validated R)
    a.rel8(0xD0, "stock")                  # BNE: still held
    a.emit(0xA9, 0x00)                      # LDA #$00
    a.emit(0x8F, *lo24(HOLD_ACTIVE_WRAM))   # STA.l $7E938B

    a.label("stock")
    a.emit(0xAD, 0x0E, 0x00)                # LDA $000E
    a.emit(0x2D, 0x0F, 0x00)                # AND $000F
    a.emit(0x5C, 0x3A, 0xAC, 0xC0)          # JML $C0AC3A
    return a.resolve()


NMI_RELEASE_HELPER = build_nmi_release_helper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips")
    args = parser.parse_args()

    rom_path = args.rom.resolve()
    base = rom_path.read_bytes()
    validate_base_rom(base)

    if base[EVENT_HOOK_FILE:EVENT_HOOK_FILE + len(EVENT_HOOK_STOCK)] != EVENT_HOOK_STOCK:
        raise SystemExit("Unexpected stock bytes at C0:012C event-engine hook")
    if base[NMI_RELEASE_HOOK_FILE:NMI_RELEASE_HOOK_FILE + len(NMI_RELEASE_HOOK_STOCK)] != NMI_RELEASE_HOOK_STOCK:
        raise SystemExit("Unexpected stock bytes at C0:AC34 NMI release hook")
    if base[SKIP_SCRIPT_FILE:SKIP_SCRIPT_FILE + len(SKIP_SCRIPT)] != b"\xFF" * len(SKIP_SCRIPT):
        raise SystemExit("Expected CA:FFC0-FFC7 intro-skip script area to be unused ($FF)")

    rom = expand_rom(base)
    rom[ROM_SIZE_OFFSET] = 0x0C
    if rom[HELPER_FILE:HELPER_RESERVED_END + 1] != b"\x00" * (HELPER_RESERVED_END - HELPER_FILE + 1):
        raise SystemExit("Expected ED:7400-74FF intro-skip helper area to be unused ($00)")
    if HELPER_FILE + len(INPUT_HELPER) - 1 >= NMI_HELPER_FILE:
        raise SystemExit("Intro-skip input helper overlaps ED:7490 NMI release helper")
    if NMI_HELPER_FILE + len(NMI_RELEASE_HELPER) - 1 > HELPER_RESERVED_END:
        raise SystemExit("Intro-skip NMI helper exceeds reserved ED:7400-74FF region")

    rom[EVENT_HOOK_FILE:EVENT_HOOK_FILE + len(EVENT_HOOK_PATCH)] = EVENT_HOOK_PATCH
    rom[NMI_RELEASE_HOOK_FILE:NMI_RELEASE_HOOK_FILE + len(NMI_RELEASE_HOOK_PATCH)] = NMI_RELEASE_HOOK_PATCH
    rom[SKIP_SCRIPT_FILE:SKIP_SCRIPT_FILE + len(SKIP_SCRIPT)] = SKIP_SCRIPT
    rom[HELPER_FILE:HELPER_FILE + len(INPUT_HELPER)] = INPUT_HELPER
    rom[NMI_HELPER_FILE:NMI_HELPER_FILE + len(NMI_RELEASE_HELPER)] = NMI_RELEASE_HELPER
    update_checksum(rom)

    patch = make_ips(base, bytes(rom))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print("Event hook: C0:012C -> JML $ED7400; return C0:0131")
    print("NMI release hook: C0:AC34 -> JML $ED7490; restore stock LDA/AND then return C0:AC3A")
    print("Intro gate: CA:0C02-0E8A")
    print("Input: hold $4218 bit $10 (runtime-validated as R) for 120 NMI frames")
    print("Timer state: $7E:938A-$938B under $CA intro scope; overlaps component 06 only under mutually exclusive $C9 scope")
    print(f"Skip script: CA:FFC0-${0xFFC0 + len(SKIP_SCRIPT) - 1:04X}")
    print(f"Input helper: ED:7400-${0x7400 + len(INPUT_HELPER) - 1:04X}")
    print(f"NMI release helper: ED:7490-${0x7490 + len(NMI_RELEASE_HELPER) - 1:04X}")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
