#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

BASE_SHA256 = '4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f'
BASE_SIZE = 0x200000
CHECKSUM_RANGE = range(0xFFDC, 0xFFE0)
ROM_SIZE_OFFSET = 0xFFD7
MERGED_THRESHOLD_OFFSET = 0x0016F6
DIRECT_FRENCH_COMPONENTS = {'02_9char_names', '03_game_select'}

ROOT = Path(__file__).resolve().parent
COMPONENTS = [
    ('tree', '01_japanese_mana_tree', 'Japanese Mana Tree restoration'),
    ('names', '02_9char_names', '9-character mixed-case names'),
    ('game-select', '03_game_select', 'French GAME SELECT'),
    ('opening', '04_french_opening', 'French opening / credits'),
    ('intro-vwf', '05_intro_vwf_french', 'French intro VWF'),
]
ALIASES = {key: folder for key, folder, _ in COMPONENTS}
ALIASES.update({folder: folder for _, folder, _ in COMPONENTS})


def parse_ips(data: bytes):
    if not data.startswith(b'PATCH'):
        raise ValueError('Not an IPS patch')
    pos = 5
    records = []
    while data[pos:pos+3] != b'EOF':
        off = int.from_bytes(data[pos:pos+3], 'big')
        size = int.from_bytes(data[pos+3:pos+5], 'big')
        pos += 5
        if size:
            payload = data[pos:pos+size]
            pos += size
        else:
            run = int.from_bytes(data[pos:pos+2], 'big')
            value = data[pos+2]
            pos += 3
            payload = bytes([value]) * run
        records.append((off, payload))
    pos += 3
    final_size = int.from_bytes(data[pos:pos+3], 'big') if len(data) >= pos + 3 else None
    return records, final_size


def patch_write_map(data: bytes):
    records, final_size = parse_ips(data)
    out = {}
    for off, payload in records:
        for i, value in enumerate(payload):
            out[off+i] = value
    return out, final_size


def apply_ips(rom: bytearray, patch: bytes):
    records, final_size = parse_ips(patch)
    for off, payload in records:
        end = off + len(payload)
        if end > len(rom):
            rom.extend(b'\0' * (end - len(rom)))
        rom[off:end] = payload
    if final_size is not None:
        if final_size > len(rom):
            rom.extend(b'\0' * (final_size - len(rom)))
        elif final_size < len(rom):
            del rom[final_size:]
    return rom


def update_checksum(rom: bytearray):
    rom[0xFFDC:0xFFE0] = b'\xff\xff\x00\x00'
    checksum = sum(rom) & 0xFFFF
    rom[0xFFDC:0xFFE0] = struct.pack('<HH', checksum ^ 0xFFFF, checksum)
    return checksum


def make_ips(base: bytes, patched: bytes):
    out = bytearray(b'PATCH')
    n = max(len(base), len(patched))
    i = 0
    while i < n:
        old = base[i] if i < len(base) else 0
        new = patched[i] if i < len(patched) else 0
        if old == new:
            i += 1
            continue
        start = i
        chunk = bytearray()
        while i < n and len(chunk) < 0xFFFF:
            old = base[i] if i < len(base) else 0
            new = patched[i] if i < len(patched) else 0
            if old == new:
                break
            chunk.append(new)
            i += 1
        out += start.to_bytes(3, 'big') + len(chunk).to_bytes(2, 'big') + chunk
    out += b'EOF'
    if len(patched) != len(base):
        out += len(patched).to_bytes(3, 'big')
    return bytes(out)


def resolve_selection(values):
    if not values or values == ['all']:
        return [folder for _, folder, _ in COMPONENTS]
    requested = []
    for value in values:
        if value == 'all':
            return [folder for _, folder, _ in COMPONENTS]
        if value not in ALIASES:
            raise SystemExit(f'Unknown component: {value}')
        folder = ALIASES[value]
        if folder not in requested:
            requested.append(folder)
    canonical = [folder for _, folder, _ in COMPONENTS]
    return [folder for folder in canonical if folder in requested]


def audit_overlaps(selected, patch_data):
    maps = {name: patch_write_map(patch_data[name])[0] for name in selected}
    errors = []
    identical = 0
    declared = 0
    for i, left in enumerate(selected):
        for right in selected[i+1:]:
            common = set(maps[left]) & set(maps[right])
            for off in common:
                # Checksums necessarily differ per standalone component and are recomputed later.
                if off in CHECKSUM_RANGE:
                    declared += 1
                    continue
                lv, rv = maps[left][off], maps[right][off]
                if lv == rv:
                    identical += 1
                    continue
                # Name Entry and GAME SELECT use the naming-safe/direct range through $E0
                # ($E1 threshold). Intro VWF extends the same canonical charset through
                # $E5 and therefore needs $E6. The combined build resolves this explicitly.
                pair = {left, right}
                if (
                    off == MERGED_THRESHOLD_OFFSET
                    and '05_intro_vwf_french' in pair
                    and bool(pair & DIRECT_FRENCH_COMPONENTS)
                ):
                    declared += 1
                    continue
                errors.append((left, right, off, lv, rv))
    if errors:
        lines = ['Undeclared patch collision(s):']
        for left, right, off, lv, rv in errors[:20]:
            lines.append(f'  {left} / {right} @ 0x{off:06X}: ${lv:02X} vs ${rv:02X}')
        raise SystemExit('\n'.join(lines))
    return identical, declared


def main():
    parser = argparse.ArgumentParser(description='Combine independent Secret of Mana French-project components safely.')
    parser.add_argument('rom', type=Path, help='clean unheadered Secret of Mana (USA) ROM')
    parser.add_argument('components', nargs='*', help='all, tree, names, game-select, opening, intro-vwf')
    parser.add_argument('-o', '--output', type=Path, default=ROOT/'build'/'patch.ips', help='combined IPS output')
    parser.add_argument('--patched-rom', type=Path, help='optional patched ROM output')
    parser.add_argument('--list', action='store_true', help='list component names and exit')
    args = parser.parse_args()

    if args.list:
        for key, folder, description in COMPONENTS:
            print(f'{key:12} {folder:26} {description}')
        return

    base = args.rom.read_bytes()
    if len(base) != BASE_SIZE or hashlib.sha256(base).hexdigest() != BASE_SHA256:
        raise SystemExit('Wrong base ROM. Expected clean unheadered Secret of Mana (USA).')

    selected = resolve_selection(args.components)
    patch_data = {name: (ROOT/'components'/name/'patch.ips').read_bytes() for name in selected}
    identical, declared = audit_overlaps(selected, patch_data)

    rom = bytearray(base)
    for name in selected:
        rom = apply_ips(rom, patch_data[name])

    # Explicit merged rule for the French direct-glyph threshold. Name Entry and
    # GAME SELECT use $E1; intro VWF extends the canonical range through $E5.
    if '05_intro_vwf_french' in selected and any(name in selected for name in DIRECT_FRENCH_COMPONENTS):
        rom[MERGED_THRESHOLD_OFFSET] = 0xE6

    checksum = update_checksum(rom)
    patch = make_ips(base, bytes(rom))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(rom)

    print('Components:')
    for name in selected:
        print(f'  - {name}')
    print(f'Compatible identical overlapping bytes: {identical}')
    print(f'Declared special/header overlapping bytes: {declared}')
    print(f'Final ROM size: 0x{len(rom):X}')
    print(f'Final checksum: ${checksum:04X}')
    print(f'IPS: {args.output}')
    print(f'IPS SHA-256: {hashlib.sha256(patch).hexdigest()}')
    if args.patched_rom:
        print(f'ROM SHA-256: {hashlib.sha256(rom).hexdigest()}')


if __name__ == '__main__':
    main()
