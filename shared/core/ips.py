"""Small IPS reader/writer used by component and aggregate builders."""
from __future__ import annotations


def parse_ips(data: bytes) -> tuple[list[tuple[int, bytes]], int | None]:
    if not data.startswith(b"PATCH"):
        raise ValueError("Not an IPS patch")
    pos = 5
    records: list[tuple[int, bytes]] = []
    while data[pos:pos + 3] != b"EOF":
        if pos + 5 > len(data):
            raise ValueError("Truncated IPS record")
        offset = int.from_bytes(data[pos:pos + 3], "big")
        size = int.from_bytes(data[pos + 3:pos + 5], "big")
        pos += 5
        if size:
            payload = data[pos:pos + size]
            if len(payload) != size:
                raise ValueError("Truncated IPS payload")
            pos += size
        else:
            if pos + 3 > len(data):
                raise ValueError("Truncated IPS RLE record")
            run = int.from_bytes(data[pos:pos + 2], "big")
            payload = bytes((data[pos + 2],)) * run
            pos += 3
        records.append((offset, payload))
    pos += 3
    final_size = int.from_bytes(data[pos:pos + 3], "big") if len(data) >= pos + 3 else None
    return records, final_size


def patch_write_map(data: bytes) -> tuple[dict[int, int], int | None]:
    records, final_size = parse_ips(data)
    writes: dict[int, int] = {}
    for offset, payload in records:
        for index, value in enumerate(payload):
            writes[offset + index] = value
    return writes, final_size


def apply_ips(rom: bytearray, patch: bytes) -> bytearray:
    records, final_size = parse_ips(patch)
    for offset, payload in records:
        end = offset + len(payload)
        if end > len(rom):
            rom.extend(b"\0" * (end - len(rom)))
        rom[offset:end] = payload
    if final_size is not None:
        if final_size > len(rom):
            rom.extend(b"\0" * (final_size - len(rom)))
        elif final_size < len(rom):
            del rom[final_size:]
    return rom


def make_ips(original: bytes, modified: bytes) -> bytes:
    """Encode changed byte runs and append an IPS truncate/expand size when needed."""
    output = bytearray(b"PATCH")
    limit = max(len(original), len(modified))
    index = 0
    while index < limit:
        old = original[index] if index < len(original) else 0
        new = modified[index] if index < len(modified) else 0
        if old == new:
            index += 1
            continue
        start = index
        payload = bytearray()
        while index < limit and len(payload) < 0xFFFF:
            old = original[index] if index < len(original) else 0
            new = modified[index] if index < len(modified) else 0
            if old == new:
                break
            payload.append(new)
            index += 1
        output += start.to_bytes(3, "big")
        output += len(payload).to_bytes(2, "big")
        output += payload
    output += b"EOF"
    if len(modified) != len(original):
        output += len(modified).to_bytes(3, "big")
    return bytes(output)
