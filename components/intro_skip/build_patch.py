#!/usr/bin/env python3
"""Build the runtime-validated hold-R intro skip component."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import MiniAssembler, lo24  # noqa: E402
from shared.core.ips import apply_ips, make_ips  # noqa: E402
from shared.core.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402

# Runtime-validated final UX: R must remain held for 120 normal-loop ticks.
HOLD_TICKS = 120

# Exact translated-intro window. $0E82 is the final $1D $7F transition into
# the separate Mode-7/flyover engine and is deliberately outside this component.
INTRO_START = 0x0C02
INTRO_TEXT_START = 0x0C0C
INTRO_PARSER_COMMIT_START = 0x0C54
INTRO_NORMAL_END = 0x0E82

# Synchronized stock pad-1 state; R is bit $10 of the low byte.
PAD1_WRAM = 0x7E0042
R_MASK = 0x10

# 16-bit state machine:
#   $FFFF = inactive / no continuous hold in progress
#   $0001-$FFFE = hold countdown in progress
#   $0000 = hold completed; skip request is committed at the next safe point
TIMER_WRAM = 0x7E938A
TIMER_INACTIVE = 0xFFFF

# Validated hooks / private code.
# Optional aggregate parser-fetch dispatcher. The standalone/runtime-proven
# intro path still hooks C0:16EA directly to CA:FFC8. When vwf_dialogues is
# present, the aggregate merge rule rewrites only that hook to ED:73C0 so parser
# mode 2 continues to ED:7500 while every other mode uses the validated intro
# helper. This keeps component patches modular and preserves dialogue preflight.
PARSER_DISPATCHER_SNES = 0xED73C0
PARSER_DISPATCHER_FILE = 0x2D73C0
PARSER_MODE_WRAM = 0x7E9380
DIALOGUE_PARSER_HELPER_SNES = 0xED7500

C0_OBSERVER_HOOK_FILE = 0x00012C
C0_OBSERVER_HOOK_STOCK = bytes.fromhex("08 E2 20 C2 10")
C0_OBSERVER_RETURN_SNES = 0xC00131
C0_OBSERVER_SNES = 0xED7488
C0_OBSERVER_FILE = 0x2D7488

PARSER_HOOK_FILE = 0x0016EA
PARSER_HOOK_STOCK = bytes.fromhex("B9 00 00 C8")
PARSER_RETURN_SNES = 0xC016EE
PARSER_HELPER_SNES = 0xCAFFC8
PARSER_HELPER_FILE = 0x0AFFC8

C2_LOOP_HOOK_FILE = 0x02C786
C2_LOOP_HOOK_STOCK = bytes.fromhex("E2 20 C2 10")
C2_LOOP_RETURN_SNES = 0xC2C78A
C2_HELPER_SNES = 0xED7400
C2_HELPER_FILE = 0x2D7400

SKIP_SCRIPT_SNES = 0xCAFFC0
SKIP_SCRIPT_FILE = 0x0AFFC0
SKIP_SCRIPT = bytes.fromhex("51 18 00 2A F8 11 06 00")

HELPER_RESERVED_START = 0x2D7400
HELPER_RESERVED_END = 0x2D74FF


def _emit_timer_inactive(a: MiniAssembler) -> None:
    a.emit(0xA9, TIMER_INACTIVE & 0xFF, TIMER_INACTIVE >> 8)  # LDA #$FFFF
    a.emit(0x8F, *lo24(TIMER_WRAM))                           # STA.l timer


def _emit_timer_start(a: MiniAssembler) -> None:
    a.emit(0xA9, HOLD_TICKS & 0xFF, HOLD_TICKS >> 8)         # LDA #hold ticks
    a.emit(0x8F, *lo24(TIMER_WRAM))                           # STA.l timer


def build_parser_dispatcher() -> bytes:
    """Aggregate-only route: dialogue mode 2 -> ED:7500, else intro helper."""
    a = MiniAssembler(PARSER_DISPATCHER_SNES)
    a.emit(0xAF, *lo24(PARSER_MODE_WRAM))
    a.emit(0xC9, 0x02)
    a.rel8(0xF0, "dialogue")
    a.emit(0x5C, *lo24(PARSER_HELPER_SNES))
    a.label("dialogue")
    a.emit(0x5C, *lo24(DIALOGUE_PARSER_HELPER_SNES))
    return a.resolve()


def build_c2_helper() -> bytes:
    """Observe/decrement R holds in the normal intro loop and commit WAIT skips."""
    a = MiniAssembler(C2_HELPER_SNES)

    # Reproduce the four stock bytes displaced at C2:C786, then preserve the
    # stock-visible processor flags while this helper performs mixed-width work.
    a.emit(0xE2, 0x20)              # SEP #$20
    a.emit(0xC2, 0x10)              # REP #$10
    a.emit(0x08)                    # PHP

    # Gate strictly to translated event $0400's normal pre-Mode-7 window.
    a.emit(0xA5, 0xD3)              # LDA $D3
    a.emit(0xC9, 0xCA)              # CMP #$CA
    a.rel8(0xD0, "done")            # BNE
    a.emit(0xC2, 0x20)              # REP #$20
    a.emit(0xA5, 0xD1)              # LDA $D1 (16-bit D1:D2)
    a.emit(0xC9, INTRO_START & 0xFF, INTRO_START >> 8)
    a.rel8(0x90, "done16")          # BCC
    a.emit(0xC9, INTRO_NORMAL_END & 0xFF, INTRO_NORMAL_END >> 8)
    a.rel8(0xB0, "done16")          # BCS

    # Once zero is reached, keep the request sticky until a validated commit
    # point consumes it; do not let a release at the same instant cancel it.
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0x00, 0x00)
    a.rel8(0xF0, "expired")

    # Hold semantics. A release at any time before zero cancels the countdown.
    a.emit(0xE2, 0x20)              # SEP #$20
    a.emit(0xAF, *lo24(PAD1_WRAM))
    a.emit(0x29, R_MASK)            # AND #R
    a.rel8(0xD0, "held")            # BNE
    a.emit(0xC2, 0x20)              # REP #$20
    _emit_timer_inactive(a)
    a.emit(0xE2, 0x20)
    a.rel8(0x80, "done")

    a.label("held")
    a.emit(0xC2, 0x20)              # REP #$20
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0xFF, 0xFF)
    a.rel8(0xD0, "counting")
    _emit_timer_start(a)
    a.emit(0xE2, 0x20)
    a.rel8(0x80, "done")

    a.label("counting")
    a.emit(0x3A)                    # DEC A (16-bit)
    a.emit(0x8F, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0x00, 0x00)
    a.rel8(0xD0, "done16")

    # C1 timed WAIT ($D0 == $82) is a validated safe commit point. Prepare the
    # private tail and let the untouched stock WAIT handler expire naturally.
    a.label("expired")
    a.emit(0xE2, 0x20)
    a.emit(0xA5, 0xD0)              # LDA $D0
    a.emit(0xC9, 0x82)              # CMP #$82
    a.rel8(0xD0, "done")
    a.emit(0xC2, 0x20)
    _emit_timer_inactive(a)         # consume completed request
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0xC0); a.emit(0x85, 0xD1)
    a.emit(0xA9, 0xFF); a.emit(0x85, 0xD2)
    a.emit(0xA9, 0xCA); a.emit(0x85, 0xD3)
    a.emit(0xA9, 0x01); a.emit(0x85, 0x4F)  # stock WAIT expires next tick
    a.rel8(0x80, "done")

    a.label("done16")
    a.emit(0xE2, 0x20)
    a.label("done")
    a.emit(0x28)                    # PLP
    a.emit(0x5C, *lo24(C2_LOOP_RETURN_SNES))
    return a.resolve()


def build_c0_observer() -> bytes:
    """Initialize/arm/cancel the same hold timer while intro text is active."""
    a = MiniAssembler(C0_OBSERVER_SNES)

    # Reproduce the full stock prologue skipped by the four-byte JML hook.
    a.emit(0x08)                    # PHP
    a.emit(0xE2, 0x20)              # SEP #$20
    a.emit(0xC2, 0x10)              # REP #$10

    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "done")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, INTRO_TEXT_START & 0xFF, INTRO_TEXT_START >> 8)
    a.rel8(0x90, "done16")
    a.emit(0xC9, INTRO_NORMAL_END & 0xFF, INTRO_NORMAL_END >> 8)
    a.rel8(0xB0, "done16")

    # WRAM is naturally zero on a fresh boot. Convert that ambiguous initial
    # zero to the explicit inactive sentinel at the first proven text entry.
    a.emit(0xC9, INTRO_TEXT_START & 0xFF, INTRO_TEXT_START >> 8)
    a.rel8(0xD0, "initialized")
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0x00, 0x00)
    a.rel8(0xD0, "initialized")
    _emit_timer_inactive(a)

    a.label("initialized")
    # Completed requests are sticky until the parser/WAIT commit consumes them.
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0x00, 0x00)
    a.rel8(0xF0, "done16")

    a.emit(0xE2, 0x20)
    a.emit(0xAF, *lo24(PAD1_WRAM))
    a.emit(0x29, R_MASK)
    a.rel8(0xD0, "held")

    # Release before completion cancels and resets the full hold duration.
    a.emit(0xC2, 0x20)
    _emit_timer_inactive(a)
    a.emit(0xE2, 0x20)
    a.rel8(0x80, "done")

    a.label("held")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0xFF, 0xFF)
    a.rel8(0xD0, "done16")          # C2 owns countdown decrement
    _emit_timer_start(a)
    a.emit(0xE2, 0x20)
    a.rel8(0x80, "done")

    a.label("done16")
    a.emit(0xE2, 0x20)
    a.label("done")
    a.emit(0x5C, *lo24(C0_OBSERVER_RETURN_SNES))
    return a.resolve()


def build_parser_helper() -> bytes:
    """Commit an already-completed hold from inside a live text carrier."""
    a = MiniAssembler(PARSER_HELPER_SNES)

    a.emit(0x08)                    # PHP
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "stock8")

    a.emit(0xC2, 0x20)
    # Start at the second carrier: the first carrier is intentionally excluded
    # so the fresh-boot zero cannot be consumed before C0 initializes $938A.
    a.emit(0xC0, INTRO_PARSER_COMMIT_START & 0xFF, INTRO_PARSER_COMMIT_START >> 8)
    a.rel8(0x90, "stock16")
    a.emit(0xC0, INTRO_NORMAL_END & 0xFF, INTRO_NORMAL_END >> 8)
    a.rel8(0xB0, "stock16")
    a.emit(0xAF, *lo24(TIMER_WRAM))
    a.emit(0xC9, 0x00, 0x00)
    a.rel8(0xD0, "stock16")

    # Consume request and redirect live parser Y to the validated tail.
    _emit_timer_inactive(a)
    a.emit(0xA0, 0xC0, 0xFF)       # LDY #$FFC0

    a.label("stock16")
    a.emit(0xE2, 0x20)
    a.label("stock8")
    a.emit(0x28)                    # PLP
    a.emit(0xB9, 0x00, 0x00)       # displaced LDA $0000,Y
    a.emit(0xC8)                    # displaced INY
    a.emit(0x5C, *lo24(PARSER_RETURN_SNES))
    return a.resolve()


PARSER_DISPATCHER = build_parser_dispatcher()
C2_HELPER = build_c2_helper()
C0_OBSERVER = build_c0_observer()
PARSER_HELPER = build_parser_helper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips")
    args = parser.parse_args()

    base = args.rom.resolve().read_bytes()
    validate_base_rom(base)

    if base[C0_OBSERVER_HOOK_FILE:C0_OBSERVER_HOOK_FILE + len(C0_OBSERVER_HOOK_STOCK)] != C0_OBSERVER_HOOK_STOCK:
        raise SystemExit("Unexpected stock bytes at C0:012C intro text observer hook")
    if base[PARSER_HOOK_FILE:PARSER_HOOK_FILE + len(PARSER_HOOK_STOCK)] != PARSER_HOOK_STOCK:
        raise SystemExit("Unexpected stock bytes at C0:16EA live parser hook")
    if base[C2_LOOP_HOOK_FILE:C2_LOOP_HOOK_FILE + len(C2_LOOP_HOOK_STOCK)] != C2_LOOP_HOOK_STOCK:
        raise SystemExit("Unexpected stock bytes at C2:C786 normal-loop hook")
    if base[SKIP_SCRIPT_FILE:SKIP_SCRIPT_FILE + 0x40] != b"\xFF" * 0x40:
        raise SystemExit("Expected CA:FFC0-FFFF intro-skip private area to be stock $FF")

    rom = expand_rom(base)
    rom[ROM_SIZE_OFFSET] = 0x0C
    if rom[HELPER_RESERVED_START:HELPER_RESERVED_END + 1] != b"\x00" * 0x100:
        raise SystemExit("Expected ED:7400-74FF intro-skip reserve to be unused ($00)")

    if rom[PARSER_DISPATCHER_FILE:PARSER_DISPATCHER_FILE + len(PARSER_DISPATCHER)] != b"\x00" * len(PARSER_DISPATCHER):
        raise SystemExit("Expected ED:73C0-73CF parser-dispatcher gap to be unused ($00)")

    if C2_HELPER_FILE + len(C2_HELPER) > C0_OBSERVER_FILE:
        raise SystemExit("C2 helper overlaps C0 observer")
    if C0_OBSERVER_FILE + len(C0_OBSERVER) > HELPER_RESERVED_END + 1:
        raise SystemExit("C0 observer exceeds ED:7400-74FF reserve")
    if PARSER_HELPER_FILE + len(PARSER_HELPER) > 0x0B0000:
        raise SystemExit("Parser helper exceeds CA:FFFF")

    # The aggregate compatibility merge may route C0:16EA through this 16-byte
    # dispatcher when vwf_dialogues is also selected. Standalone intro_skip keeps
    # the exact runtime-proven direct C0:16EA -> CA:FFC8 hook below.
    rom[PARSER_DISPATCHER_FILE:PARSER_DISPATCHER_FILE + len(PARSER_DISPATCHER)] = PARSER_DISPATCHER

    # Hooks. C0:012C's helper reproduces 5 stock prologue bytes and returns at
    # C0:0131; the other two helpers reproduce exactly their displaced bytes.
    rom[C0_OBSERVER_HOOK_FILE:C0_OBSERVER_HOOK_FILE + 4] = bytes((0x5C, *lo24(C0_OBSERVER_SNES)))
    rom[PARSER_HOOK_FILE:PARSER_HOOK_FILE + 4] = bytes((0x5C, *lo24(PARSER_HELPER_SNES)))
    rom[C2_LOOP_HOOK_FILE:C2_LOOP_HOOK_FILE + 4] = bytes((0x5C, *lo24(C2_HELPER_SNES)))

    rom[SKIP_SCRIPT_FILE:SKIP_SCRIPT_FILE + len(SKIP_SCRIPT)] = SKIP_SCRIPT
    rom[PARSER_HELPER_FILE:PARSER_HELPER_FILE + len(PARSER_HELPER)] = PARSER_HELPER
    rom[C2_HELPER_FILE:C2_HELPER_FILE + len(C2_HELPER)] = C2_HELPER
    rom[C0_OBSERVER_FILE:C0_OBSERVER_FILE + len(C0_OBSERVER)] = C0_OBSERVER

    update_checksum(rom)
    patch = make_ips(base, bytes(rom))
    if apply_ips(bytearray(base), patch) != rom:
        raise AssertionError("IPS self-application failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print(f"Validated hold duration: {HOLD_TICKS} normal-loop ticks")
    print("Pad source: $7E:0042 bit $10 (R)")
    print("Validated normal-intro window: CA:0C02-0E81; final Mode-7 phase excluded")
    print(f"Aggregate parser dispatcher: ED:73C0-${0x73C0 + len(PARSER_DISPATCHER) - 1:04X} ({len(PARSER_DISPATCHER)} bytes)")
    print(f"C2 helper: ED:7400-${0x7400 + len(C2_HELPER) - 1:04X} ({len(C2_HELPER)} bytes)")
    print(f"C0 observer: ED:7488-${0x7488 + len(C0_OBSERVER) - 1:04X} ({len(C0_OBSERVER)} bytes)")
    print(f"Skip tail: CA:FFC0-${0xFFC0 + len(SKIP_SCRIPT) - 1:04X}")
    print(f"Parser helper: CA:FFC8-${0xFFC8 + len(PARSER_HELPER) - 1:04X} ({len(PARSER_HELPER)} bytes)")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
