"""Extended-bank relocation support for edited stock event scripts.

The stock event dispatcher resolves IDs $0000-$07FF to a 16-bit pointer in
bank $C9 or $CA.  Component 08 leaves that path untouched unless at least one
edited event no longer fits its original pointer span.

When relocation is required, a tiny dispatcher hook first consults a sparse
2048-entry 24-bit table in expanded ROM.  A zero bank byte means "use the stock
$C9/$CA lookup"; a non-zero entry supplies the complete relocated event address.
This preserves every stock pointer (including component-05's runtime-validated
$0400-$040F changes) for events that component 08 does not relocate.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.asm65816 import MiniAssembler, lo24

EVENT_COUNT = 0x800

# Stock event-ID dispatcher in bank C1.  At this point the 16-bit event ID has
# already been stored in direct-page $00 and M/X are 16-bit.  The six-byte hook
# calls our resolver, then skips only the stock bank/pointer selection block and
# resumes at $C1:E7BA.
EVENT_LOADER_HOOK_FILE = 0x01E794
EVENT_LOADER_HOOK_CPU = 0xC1E794
EVENT_LOADER_CONTINUE_CPU = 0xC1E7BA
EVENT_LOADER_SIGNATURE = bytes.fromhex("A5 00 C9 00 04 08")

# Expanded-ROM ownership.  E8:0000-$17FF is a sparse 3-byte pointer table,
# E8:1800-$1FFF is reserved for the loader helper, and relocated event payloads
# are packed from E8:2000 through EC:FFFF.  ED and above are already used by
# existing components.
RELOCATION_TABLE_FILE = 0x280000
RELOCATION_TABLE_CPU = 0xE80000
RELOCATION_TABLE_SIZE = EVENT_COUNT * 3  # $1800
RELOCATION_HELPER_FILE = 0x281800
RELOCATION_HELPER_CPU = 0xE81800
RELOCATION_HELPER_RESERVED_END = 0x282000
RELOCATION_DATA_START_FILE = 0x282000
RELOCATION_DATA_END_FILE = 0x2D0000  # exclusive: banks E8-EC only
RELOCATION_BANK_FIRST = 0xE8
RELOCATION_BANK_END_EXCLUSIVE = 0xED


@dataclass(frozen=True)
class RelocatedEvent:
    event_id: int
    file_offset: int
    cpu_address: int
    data: bytes


def _assemble_event_loader_helper() -> bytes:
    """Return the sparse relocation-table resolver.

    Input contract is the stock dispatcher state at $C1:E794: event ID is in
    direct-page $00 and M/X are 16-bit. Output matches the stock block: $D1/D2
    hold the 16-bit event pointer, $D3 its bank, A is 8-bit with the bank in its
    low byte, and X holds the original 2-byte stock pointer-table index.
    """
    a = MiniAssembler(RELOCATION_HELPER_CPU)

    # table_index = event_id * 3
    a.emit(0xC2, 0x30)                     # REP #$30
    a.emit(0xA5, 0x00)                     # LDA $00
    a.emit(0x0A)                           # ASL -> id * 2
    a.emit(0x18)                           # CLC
    a.emit(0x65, 0x00)                     # ADC $00 -> id * 3
    a.emit(0xAA)                           # TAX

    # A non-zero bank byte marks a relocated event.
    a.emit(0xE2, 0x20)                     # SEP #$20
    a.emit(0xBF, *lo24(RELOCATION_TABLE_CPU + 2))
    a.rel8(0xF0, "stock")                 # zero bank -> stock lookup
    a.emit(0x85, 0xD3)                     # STA $D3
    a.emit(0xC2, 0x20)                     # REP #$20
    a.emit(0xBF, *lo24(RELOCATION_TABLE_CPU))
    a.emit(0x85, 0xD1)                     # STA $D1/$D2

    # Match the stock block's transient register state too. Stock leaves X at
    # the 2-byte pointer-table index, then switches A to 8-bit and loads the
    # selected bank while the hidden B byte still contains pointer high. Save
    # and restore the relocated pointer around the X calculation to reproduce
    # that contract instead of assuming the continuation ignores it.
    a.emit(0x48)                           # PHA relocated 16-bit pointer
    a.emit(0xA5, 0x00)                     # LDA event ID
    a.emit(0x29, 0xFF, 0x03)               # AND #$03FF
    a.emit(0x0A)                           # * 2
    a.emit(0xAA)                           # TAX
    a.emit(0x68)                           # PLA relocated pointer
    a.emit(0xE2, 0x20)                     # stock continuation expects 8-bit A
    a.emit(0xA5, 0xD3)                     # A low = bank; B stays pointer high
    a.emit(0x6B)                           # RTL

    # Reproduce the stock C9/CA pointer selection exactly for every sparse-table
    # miss.  Reading the *live* stock tables is important: component 05 rewrites
    # $0401-$040F pointers, and those changes must remain authoritative.
    a.label("stock")
    a.emit(0xC2, 0x30)                     # REP #$30
    a.emit(0xA5, 0x00)                     # LDA event ID
    a.emit(0xC9, 0x00, 0x04)               # CMP #$0400
    a.rel8(0xB0, "ca")                    # BCS CA table

    a.emit(0x0A)                           # C9 index = id * 2
    a.emit(0xAA)
    a.emit(0xBF, 0x00, 0x00, 0xC9)         # LDA.l $C90000,X
    a.emit(0x85, 0xD1)
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0xC9)
    a.emit(0x85, 0xD3)
    a.emit(0x6B)

    a.label("ca")
    a.emit(0x29, 0xFF, 0x03)               # AND #$03FF
    a.emit(0x0A)
    a.emit(0xAA)
    a.emit(0xBF, 0x00, 0x00, 0xCA)         # LDA.l $CA0000,X
    a.emit(0x85, 0xD1)
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0xCA)
    a.emit(0x85, 0xD3)
    a.emit(0x6B)

    return a.resolve()


EVENT_LOADER_HELPER = _assemble_event_loader_helper()
_HOOK_BRANCH_NEXT_CPU = EVENT_LOADER_HOOK_CPU + 6
_HOOK_BRANCH_DISPLACEMENT = EVENT_LOADER_CONTINUE_CPU - _HOOK_BRANCH_NEXT_CPU
if not -128 <= _HOOK_BRANCH_DISPLACEMENT <= 127:
    raise ValueError("event-loader continuation is out of BRA range")
EVENT_LOADER_HOOK = bytes(
    [0x22, *lo24(RELOCATION_HELPER_CPU), 0x80, _HOOK_BRANCH_DISPLACEMENT & 0xFF]
)

# Keep these checks close to the generated payload so a future address change
# fails immediately.
if len(EVENT_LOADER_HOOK) != len(EVENT_LOADER_SIGNATURE):
    raise ValueError("event-loader hook must replace exactly six stock bytes")
if RELOCATION_HELPER_FILE + len(EVENT_LOADER_HELPER) > RELOCATION_HELPER_RESERVED_END:
    raise ValueError("event-loader helper exceeds reserved E8:1800-$1FFF block")


def validate_stock(base: bytes) -> None:
    actual = bytes(base[EVENT_LOADER_HOOK_FILE:EVENT_LOADER_HOOK_FILE + len(EVENT_LOADER_SIGNATURE)])
    if actual != EVENT_LOADER_SIGNATURE:
        raise SystemExit(
            "Unexpected clean-US event-loader signature at "
            f"0x{EVENT_LOADER_HOOK_FILE:06X}: {actual.hex(' ').upper()}"
        )


def _cpu_address(file_offset: int) -> int:
    # HiROM C0-FF mirror: file 0x280000 -> CPU $E8:0000.
    return 0xC00000 + file_offset


def pack_events(items: list[tuple[int, bytes]]) -> list[RelocatedEvent]:
    """Pack ``(event_id, data)`` pairs deterministically into E8-EC.

    No event may cross a 64 KiB bank boundary because the stock event pointer is
    a 16-bit offset plus a separate bank byte and increments without bank carry.
    """
    cursor = RELOCATION_DATA_START_FILE
    packed: list[RelocatedEvent] = []

    for event_id, data in sorted(items):
        if not 0 <= event_id < EVENT_COUNT:
            raise ValueError(f"relocation event ID out of range: ${event_id:04X}")
        if not data:
            raise ValueError(f"event ${event_id:04X}: cannot relocate an empty script")
        if len(data) > 0x10000:
            raise ValueError(f"event ${event_id:04X}: script exceeds one 64 KiB bank")

        bank_end = (cursor & ~0xFFFF) + 0x10000
        if cursor + len(data) > bank_end:
            cursor = bank_end
        if cursor < RELOCATION_DATA_START_FILE or cursor + len(data) > RELOCATION_DATA_END_FILE:
            raise ValueError(
                f"event ${event_id:04X}: relocated event pool E8:2000-EC:FFFF is full"
            )

        cpu = _cpu_address(cursor)
        bank = (cpu >> 16) & 0xFF
        if not RELOCATION_BANK_FIRST <= bank < RELOCATION_BANK_END_EXCLUSIVE:
            raise ValueError(f"event ${event_id:04X}: relocation escaped reserved banks: ${bank:02X}")

        packed.append(RelocatedEvent(event_id, cursor, cpu, bytes(data)))
        cursor += len(data)

    return packed


def install(rom: bytearray, relocated: list[RelocatedEvent]) -> None:
    """Install the dispatcher hook, helper, sparse table entries and payloads."""
    if not relocated:
        return
    if len(rom) < RELOCATION_DATA_END_FILE:
        raise ValueError("ROM must be expanded before installing event relocation")

    # Expanded ROM is zero-filled by the patchkit.  The sparse table therefore
    # needs writes only for actual relocated entries; explicitly clearing the
    # logical table here keeps direct builder calls deterministic too.
    rom[RELOCATION_TABLE_FILE:RELOCATION_TABLE_FILE + RELOCATION_TABLE_SIZE] = bytes(RELOCATION_TABLE_SIZE)
    rom[RELOCATION_HELPER_FILE:RELOCATION_HELPER_FILE + len(EVENT_LOADER_HELPER)] = EVENT_LOADER_HELPER
    rom[EVENT_LOADER_HOOK_FILE:EVENT_LOADER_HOOK_FILE + len(EVENT_LOADER_HOOK)] = EVENT_LOADER_HOOK

    seen: set[int] = set()
    for item in relocated:
        if item.event_id in seen:
            raise ValueError(f"duplicate relocated event ${item.event_id:04X}")
        seen.add(item.event_id)

        rom[item.file_offset:item.file_offset + len(item.data)] = item.data
        entry = RELOCATION_TABLE_FILE + item.event_id * 3
        rom[entry:entry + 3] = bytes(
            (item.cpu_address & 0xFF, (item.cpu_address >> 8) & 0xFF, (item.cpu_address >> 16) & 0xFF)
        )
