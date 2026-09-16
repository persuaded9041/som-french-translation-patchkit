"""Shared dispatch state for non-dialogue UI VWF components.

The stock renderer entry at $C0:167D is shared by ordinary event text and several
menu/UI callers.  `vwf_dialogues` and `vwf_ui` both install the
same tiny dispatcher so their standalone patches remain self-contained and their
aggregate overlap is byte-identical.

Component-specific renderers remain independent:
- `vwf_dialogues`: $ED:7040
- `vwf_ui`: $ED:7B00
"""
from __future__ import annotations

from shared.core.asm import MiniAssembler, lo24

RENDER_ENTRY_FILE = 0x00167D
RENDER_ENTRY_SIGNATURE = bytes.fromhex("A9 20 8D 76 A1")

DISPATCH_CPU = 0xED7A00
DISPATCH_FILE = 0x2D7A00
DISPATCH_RESERVED_SIZE = 0x80

UI_RENDER_CPU = 0xED7B00
DIALOGUE_RENDER_CPU = 0xED7040

# Shared C7 config gap immediately after existing intro/dialogue/name-DTE bytes.
UI_CONFIG_CPU = 0xC74C87
UI_CONFIG_FILE = 0x074C87
UI_MARKER = 0x09

# One-shot WRAM identity tag set only by a proven UI builder.
UI_TAG = 0x93C1
FORGE_UI_MAGIC = 0xA7
RING_UI_MAGIC = 0xA8
# Backward-compatible alias for code that still refers to the validated Forge tag.
UI_MAGIC = FORGE_UI_MAGIC

DIALOGUE_CONFIG_CPU = 0xC74C84
DIALOGUE_MARKER = 0x06


def _assemble_dispatcher() -> bytes:
    a = MiniAssembler(DISPATCH_CPU)

    # UI has first refusal only when `vwf_ui` is installed *and* its exact
    # builder has armed the one-shot tag.
    a.emit(0xAF, *lo24(UI_CONFIG_CPU))
    a.emit(0xC9, UI_MARKER)
    a.rel8(0xD0, "dialogue")
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, FORGE_UI_MAGIC)
    a.rel8(0xF0, "ui")
    a.emit(0xC9, RING_UI_MAGIC)
    a.rel8(0xF0, "ui")

    a.label("dialogue")
    # `vwf_dialogues` sets its existing shared parser config marker. If present,
    # defer to its runtime-validated entry classifier unchanged.
    a.emit(0xAF, *lo24(DIALOGUE_CONFIG_CPU))
    a.emit(0xC9, DIALOGUE_MARKER)
    a.rel8(0xF0, "dialogue_vwf")

    # No VWF owner: clear any stale low-level VWF scope left by a previous
    # one-shot UI render, then replay the stock entry bytes and continue at
    # $C0:1682.  This is required for standalone `vwf_ui`: GAME SELECT
    # and other stock callers share the same character hooks but must see
    # $9385 == 0.
    a.emit(0x9C, 0x85, 0x93)
    a.emit(0xA9, 0x20)
    a.emit(0x8D, 0x76, 0xA1)
    a.emit(0x5C, *lo24(0xC01682))

    a.label("ui")
    a.emit(0x5C, *lo24(UI_RENDER_CPU))

    a.label("dialogue_vwf")
    a.emit(0x5C, *lo24(DIALOGUE_RENDER_CPU))
    return a.resolve()


DISPATCHER = _assemble_dispatcher()
RENDER_ENTRY_HOOK = bytes([0x5C, *lo24(DISPATCH_CPU)])


def validate_stock(base: bytes) -> None:
    if base[RENDER_ENTRY_FILE:RENDER_ENTRY_FILE + len(RENDER_ENTRY_SIGNATURE)] != RENDER_ENTRY_SIGNATURE:
        raise SystemExit("Unexpected clean-US shared renderer-entry signature")
    if base[UI_CONFIG_FILE] != 0xFF:
        raise SystemExit("Expected stock-$FF UI VWF config byte")
    if len(DISPATCHER) > DISPATCH_RESERVED_SIZE:
        raise SystemExit("Shared UI/dialogue renderer dispatcher is too large")


def install_dispatcher(rom: bytearray) -> None:
    rom[RENDER_ENTRY_FILE:RENDER_ENTRY_FILE + len(RENDER_ENTRY_HOOK)] = RENDER_ENTRY_HOOK
    rom[DISPATCH_FILE:DISPATCH_FILE + len(DISPATCHER)] = DISPATCHER


def enable_ui(rom: bytearray) -> None:
    rom[UI_CONFIG_FILE] = UI_MARKER
