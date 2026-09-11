#!/usr/bin/env python3
"""Build the editable default Name Entry prefill component."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.ips import make_ips  # noqa: E402
from shared.rom import update_checksum, validate_base_rom  # noqa: E402

HOOK_OFFSET = 0x075039
HOOK_EXPECTED = bytes.fromhex("9C CC A1 6B")  # STZ $A1CC / RTL
HOOK_PAYLOAD = bytes.fromhex("5C 30 46 C7")   # JML $C7:4630
HELPER_OFFSET = 0x074630
HELPER_LIMIT = 0x0746A1
DATA_OFFSET = 0x0746D0
RECORD_SIZE = 8
ROLE_ORDER = ("boy", "girl", "sprite")
MAX_PREFILL_NAME = RECORD_SIZE - 1

# See src/prefill.asm. Machine code is fixed; localized/default content lives
# only in the records generated from assets/name_entry_defaults.json.
HELPER = bytes.fromhex(
    "08 C2 10 DA 5A AE 59 A1 DA E2 20 9C CC A1 9C CD A1 "
    "AD 2B A2 C9 03 B0 4E 0A 0A 0A AA BF D0 46 C7 29 0F "
    "8D CD A1 F0 3F E8 BF D0 46 C7 48 29 1F 0A 0A 0A 18 "
    "69 13 8D 59 A1 68 30 06 AF 19 50 C7 80 07 AF 19 50 "
    "C7 18 69 10 8D 5A A1 DA 22 E0 50 C7 B0 0D 22 24 51 "
    "C7 EE 57 A1 EE 57 A1 EE CC A1 FA E8 CE CD A1 D0 C2 "
    "9C CD A1 FA 8E 59 A1 7A FA 28 6B"
)
assert HELPER_OFFSET + len(HELPER) == HELPER_LIMIT


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
        raise SystemExit(f"{path} must contain exactly {', '.join(ROLE_ORDER)} ({'; '.join(bits)})")
    result: dict[str, str] = {}
    for role in ROLE_ORDER:
        value = raw[role]
        if not isinstance(value, str) or not value:
            raise SystemExit(f"{role}: default name must be a non-empty string")
        if len(value) > MAX_PREFILL_NAME:
            raise SystemExit(
                f"{role}: {value!r} has {len(value)} characters; current prefill record supports at most {MAX_PREFILL_NAME}"
            )
        if any(not ("A" <= ch <= "Z" or "a" <= ch <= "z") for ch in value):
            raise SystemExit(f"{role}: {value!r} contains unsupported characters; this foundation accepts ASCII letters only")
        result[role] = value
    return result


def token_for_char(ch: str) -> int:
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A")
    if "a" <= ch <= "z":
        return 0x80 | (ord(ch) - ord("a"))
    raise AssertionError(ch)


def build_records(defaults: dict[str, str]) -> bytes:
    out = bytearray()
    for role in ROLE_ORDER:
        name = defaults[role]
        tokens = [token_for_char(ch) for ch in name]
        record = bytes([len(tokens), *tokens])
        record += bytes(RECORD_SIZE - len(record))
        assert len(record) == RECORD_SIZE
        out += record
    return bytes(out)


def verify_stock_space(base: bytes) -> None:
    hook = base[HOOK_OFFSET:HOOK_OFFSET + len(HOOK_EXPECTED)]
    if hook != HOOK_EXPECTED:
        raise SystemExit(
            f"Unexpected Name Entry init tail at {HOOK_OFFSET:#08x}: expected {HOOK_EXPECTED.hex(' ')}, got {hook.hex(' ')}"
        )
    for start, size, label in (
        (HELPER_OFFSET, len(HELPER), "prefill helper"),
        (DATA_OFFSET, RECORD_SIZE * len(ROLE_ORDER), "prefill data"),
    ):
        actual = base[start:start + size]
        if actual != bytes([0xFF]) * size:
            raise SystemExit(f"Clean-USA {label} reserve at {start:#08x} is not all $FF")


def apply(base: bytes, records: bytes) -> bytearray:
    verify_stock_space(base)
    rom = bytearray(base)
    rom[HOOK_OFFSET:HOOK_OFFSET + len(HOOK_PAYLOAD)] = HOOK_PAYLOAD
    rom[HELPER_OFFSET:HELPER_OFFSET + len(HELPER)] = HELPER
    rom[DATA_OFFSET:DATA_OFFSET + len(records)] = records
    update_checksum(rom)
    return rom


def main() -> None:
    parser = argparse.ArgumentParser(description="Build editable default names for Secret of Mana Name Entry.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    defaults = load_defaults(ROOT / "assets" / "name_entry_defaults.json")
    records = build_records(defaults)
    patched = apply(base, records)
    ips = make_ips(base, patched)

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else ROOT / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Patched ROM: {patched_path}")

    print(f"Base ROM verified: {args.rom}")
    for role in ROLE_ORDER:
        print(f"Default {role}: {defaults[role]}")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")


if __name__ == "__main__":
    main()
