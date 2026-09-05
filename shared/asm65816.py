"""Tiny helpers for Python-generated 65C816 machine-code payloads."""
from __future__ import annotations

import struct


class MiniAssembler:
    """Minimal label-aware emitter for relative 8/16-bit branches."""

    def __init__(self, origin: int):
        self.origin = origin
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, int]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.data)

    def emit(self, *values: int) -> None:
        self.data.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = self.pc

    def rel8(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.data) - 1, label, 1))

    def rel16(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0, 0)
        self.fixups.append((len(self.data) - 2, label, 2))

    def resolve(self) -> bytes:
        for pos, label, size in self.fixups:
            if label not in self.labels:
                raise ValueError(f"unknown label: {label}")
            target = self.labels[label]
            operand_cpu = self.origin + pos
            next_cpu = operand_cpu + size
            displacement = target - next_cpu
            if size == 1:
                if not -128 <= displacement <= 127:
                    raise ValueError(f"8-bit branch to {label} is out of range: {displacement}")
                self.data[pos] = displacement & 0xFF
            elif size == 2:
                if not -32768 <= displacement <= 32767:
                    raise ValueError(f"16-bit branch to {label} is out of range: {displacement}")
                self.data[pos : pos + 2] = struct.pack("<h", displacement)
            else:
                raise ValueError(f"unsupported relative operand size: {size}")
        return bytes(self.data)


def lo16(value: int) -> tuple[int, int]:
    """Return the low 16 bits as little-endian bytes."""
    return value & 0xFF, (value >> 8) & 0xFF


def lo24(value: int) -> tuple[int, int, int]:
    """Return the low 24 bits as little-endian bytes."""
    return value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF
