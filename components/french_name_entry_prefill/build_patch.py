#!/usr/bin/env python3
"""Build the French editable default-name prefill overlay."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import MiniAssembler, lo24  # noqa: E402
from shared.core.ips import apply_ips, make_ips  # noqa: E402
from shared.build.dependency_overlay import make_dependency_overlay  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402

HELPER_OFFSET = 0x074630
HELPER_ORIGIN = 0xC74630
HELPER_LIMIT = 0x0746D0
DATA_OFFSET = 0x0746D0
RECORD_SIZE = 8
ROLE_ORDER = ("boy", "girl", "sprite")
MAX_PREFILL_NAME = RECORD_SIZE - 1
GENERIC_HELPER_END = 0x0746A1
GENERIC_DATA_END = DATA_OFFSET + RECORD_SIZE * len(ROLE_ORDER)
PREFILL_SIZE = RECORD_SIZE * len(ROLE_ORDER)


def load_defaults(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    if set(raw) != set(ROLE_ORDER):
        missing = sorted(set(ROLE_ORDER) - set(raw))
        extra = sorted(set(raw) - set(ROLE_ORDER))
        bits = []
        if missing:
            bits.append("missing: " + ", ".join(missing))
        if extra:
            bits.append("unexpected: " + ", ".join(extra))
        raise SystemExit(
            f"{path} must contain exactly {', '.join(ROLE_ORDER)} ({'; '.join(bits)})"
        )
    result: dict[str, str] = {}
    for role in ROLE_ORDER:
        value = raw[role]
        if not isinstance(value, str) or not value:
            raise SystemExit(f"{role}: default name must be a non-empty string")
        if len(value) > MAX_PREFILL_NAME:
            raise SystemExit(
                f"{role}: {value!r} has {len(value)} characters; current prefill record supports at most {MAX_PREFILL_NAME}"
            )
        result[role] = value
    return result


def load_extension_row() -> str:
    path = PROJECT_ROOT / "components" / "french_name_entry_extended" / "assets" / "name_entry_extension.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"row"} or not isinstance(raw["row"], str):
        raise SystemExit(f"{path} must contain exactly one string field: row")
    if len(raw["row"]) > 26:
        raise SystemExit(f"French Name Entry extension row has {len(raw['row'])} entries; at most 26 are supported")
    return raw["row"]


def token_for_char(ch: str, extension_row: str) -> int:
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A")
    if "a" <= ch <= "z":
        return 0x80 | (ord(ch) - ord("a"))
    index = extension_row.find(ch)
    if index >= 0:
        return 0xC0 | index
    raise SystemExit(
        f"Unsupported French prefill character {ch!r}; it is not present in the generic alphabet or French extension row"
    )


def build_records(defaults: dict[str, str], extension_row: str) -> bytes:
    out = bytearray()
    for role in ROLE_ORDER:
        name = defaults[role]
        tokens = [token_for_char(ch, extension_row) for ch in name]
        record = bytes([len(tokens), *tokens])
        record += bytes(RECORD_SIZE - len(record))
        assert len(record) == RECORD_SIZE
        out += record
    return bytes(out)


def build_helper() -> bytes:
    """Emit the generic helper plus a token class for the French fourth row."""
    a = MiniAssembler(HELPER_ORIGIN)
    data_addr = 0xC746D0
    selector_addr = 0xC75019

    a.emit(0x08)                         # PHP
    a.emit(0xC2, 0x10)                   # REP #$10
    a.emit(0xDA, 0x5A)                   # PHX / PHY
    a.emit(0xAE, 0x59, 0xA1)             # LDX $A159
    a.emit(0xDA)                         # PHX
    a.emit(0xE2, 0x20)                   # SEP #$20
    a.emit(0x9C, 0xCC, 0xA1)             # STZ $A1CC
    a.emit(0x9C, 0xCD, 0xA1)             # STZ $A1CD

    a.emit(0xAD, 0x2B, 0xA2)             # LDA $A22B
    a.emit(0xC9, 0x03)                   # CMP #$03
    a.rel8(0xB0, "restore")             # BCS .restore
    a.emit(0x0A, 0x0A, 0x0A)             # ASL x3
    a.emit(0xAA)                         # TAX
    a.emit(0xBF, *lo24(data_addr))        # LDA.l data,x
    a.emit(0x29, 0x0F)                   # AND #$0F
    a.emit(0x8D, 0xCD, 0xA1)             # STA $A1CD
    a.rel8(0xF0, "restore")             # BEQ .restore
    a.emit(0xE8)                         # INX

    a.label("loop")
    a.emit(0xBF, *lo24(data_addr))        # LDA.l data,x
    a.emit(0x48)                         # PHA
    a.emit(0x29, 0x1F)                   # AND #$1F
    a.emit(0x0A, 0x0A, 0x0A)             # ASL x3
    a.emit(0x18)                         # CLC
    a.emit(0x69, 0x13)                   # ADC #$13
    a.emit(0x8D, 0x59, 0xA1)             # STA $A159
    a.emit(0x68)                         # PLA
    a.emit(0x29, 0xC0)                   # AND #$C0
    a.emit(0xC9, 0xC0)                   # CMP #$C0
    a.rel8(0xF0, "extension")           # BEQ .extension
    a.emit(0xC9, 0x80)                   # CMP #$80
    a.rel8(0xF0, "lower")               # BEQ .lower

    a.label("upper")
    a.emit(0xAF, *lo24(selector_addr))    # LDA.l $C75019
    a.rel8(0x80, "row_done")            # BRA .row_done

    a.label("lower")
    a.emit(0xAF, *lo24(selector_addr))
    a.emit(0x18)                         # CLC
    a.emit(0x69, 0x10)                   # ADC #$10
    a.rel8(0x80, "row_done")

    a.label("extension")
    a.emit(0xAF, *lo24(selector_addr))
    a.emit(0x18)                         # CLC
    a.emit(0x69, 0x30)                   # ADC #$30

    a.label("row_done")
    a.emit(0x8D, 0x5A, 0xA1)             # STA $A15A
    a.emit(0xDA)                         # PHX
    a.emit(0x22, *lo24(0xC750E0))        # JSL $C750E0
    a.rel8(0xB0, "skip_insert")         # BCS .skip_insert
    a.emit(0x22, *lo24(0xC75124))        # JSL $C75124
    a.emit(0xEE, 0x57, 0xA1)             # INC $A157
    a.emit(0xEE, 0x57, 0xA1)
    a.emit(0xEE, 0xCC, 0xA1)             # INC $A1CC

    a.label("skip_insert")
    a.emit(0xFA)                         # PLX
    a.emit(0xE8)                         # INX
    a.emit(0xCE, 0xCD, 0xA1)             # DEC $A1CD
    a.rel8(0xD0, "loop")                # BNE .loop

    a.label("restore")
    a.emit(0x9C, 0xCD, 0xA1)             # STZ $A1CD
    a.emit(0xFA)                         # PLX
    a.emit(0x8E, 0x59, 0xA1)             # STX $A159
    a.emit(0x7A, 0xFA, 0x28, 0x6B)       # PLY / PLX / PLP / RTL

    helper = a.resolve()
    if HELPER_OFFSET + len(helper) > HELPER_LIMIT:
        raise SystemExit(
            f"French prefill helper ends at {HELPER_OFFSET + len(helper):#08x}; data starts at {HELPER_LIMIT:#08x}"
        )
    return helper


def verify_stock_space(base: bytes, helper: bytes) -> None:
    if HELPER_OFFSET + len(helper) > HELPER_LIMIT:
        raise AssertionError("French prefill helper exceeds its reserved helper range")
    # This overlay is built from the clean USA ROM like all component IPS files.
    # It intentionally overrides the dependency's helper/data only when combined.
    actual = base[HELPER_OFFSET:HELPER_OFFSET + len(helper)]
    if actual != bytes([0xFF]) * len(helper):
        raise SystemExit(f"Clean-USA French prefill helper reserve at {HELPER_OFFSET:#08x} is not all $FF")
    actual = base[DATA_OFFSET:GENERIC_DATA_END]
    if actual != bytes([0xFF]) * (GENERIC_DATA_END - DATA_OFFSET):
        raise SystemExit(f"Clean-USA French prefill data reserve at {DATA_OFFSET:#08x} is not all $FF")


def apply(base: bytes, helper: bytes, records: bytes) -> bytearray:
    verify_stock_space(base, helper)
    if len(records) != PREFILL_SIZE:
        raise AssertionError("French prefill records do not fill their reserved range")
    rom = bytearray(base)
    rom[HELPER_OFFSET:HELPER_OFFSET + len(helper)] = helper
    rom[DATA_OFFSET:DATA_OFFSET + len(records)] = records
    update_checksum(rom)
    return rom


def main() -> None:
    parser = argparse.ArgumentParser(description="Build French editable default names for Secret of Mana Name Entry.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional overlay-only patched ROM output (dependencies not included)")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    defaults = load_defaults(ROOT / "assets" / "name_entry_defaults_fr.json")
    extension_row = load_extension_row()
    records = build_records(defaults, extension_row)
    helper = build_helper()
    patched = apply(base, helper, records)
    full_ips = make_ips(base, patched)
    if apply_ips(bytearray(base), full_ips) != patched:
        raise AssertionError("IPS self-application failed")
    ips = make_dependency_overlay(
        base,
        args.rom.resolve(),
        [
            PROJECT_ROOT / "components" / "default_name_entry_extended",
            PROJECT_ROOT / "components" / "default_name_entry_prefill",
        ],
        full_ips,
    )

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else ROOT / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Overlay-only ROM (requires declared dependencies for use): {patched_path}")

    print(f"Base ROM verified: {args.rom}")
    print("Dependencies: default_name_entry_prefill, french_name_entry_extended")
    for role in ROLE_ORDER:
        print(f"French default {role}: {defaults[role]}")
    print(f"French helper: {len(helper)} bytes")
    print(f"IPS: {output}")
    print(f"Dependency delta IPS size: {len(ips)} bytes")


if __name__ == "__main__":
    main()
