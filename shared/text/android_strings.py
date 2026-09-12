"""Read Android scrtxt/systxt string-table binaries used by the project."""
from __future__ import annotations

from pathlib import Path
import struct


def read_string_table(path: Path) -> dict[int, str]:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path}: file too small")
    count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + count * 8
    if table_end + pool_size != len(data):
        raise ValueError(f"{path}: inconsistent scrtxt/systxt size")
    pool = data[table_end:]
    out: dict[int, str] = {}
    for index in range(count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id in out or offset >= len(pool):
            raise ValueError(f"{path}: invalid table record {index}")
        end = pool.find(b"\0", offset)
        if end < 0:
            raise ValueError(f"{path}: unterminated text {text_id}")
        out[text_id] = pool[offset:end].decode("utf-8")
    return out
