"""Shared low-level VWF renderer runtime used by standalone UI VWF.

These bytes are the runtime-validated generic rendering core already used by
component 06.  They are frozen here so component 09 can install the same
character/row/outline machinery without depending on component 06 itself.
The active scope is selected at runtime through WRAM $7E:9385; when inactive,
the hooks replay stock behavior.
"""
from __future__ import annotations
CHAR_START_FILE = 0x001686
FONT_ROW_FILE = 0x0016A4
CHAR_END_FILE = 0x0016B1
OUTLINE_POST_FILE = 0x001168
CHAR_START_HELPER_FILE = 0x2D7180
CHAR_END_HELPER_FILE = 0x2D70C0
FONT_ROW_HELPER_FILE = 0x2D7100
WIDTH_TABLE_FILE = 0x2D7200
OUTLINE_POST_HELPER_FILE = 0x2D7280
CHUNK_COMMIT_HELPER_FILE = 0x2D7340
CHUNK_CELLS_SNAPSHOT_FILE = 0x2D7380
EVENT_RENDER_SCOPE_HELPER_FILE = 0x2D73B0
CHOICE_VISUAL_HELPER_FILE = 0x2D7880
CHOICE_TRACKER_HELPER_FILE = 0x2D7910

CHAR_START_SIGNATURE = bytes.fromhex("bd a4 a1 e8")
FONT_ROW_SIGNATURE = bytes.fromhex("bf 00 dc d2")
CHAR_END_SIGNATURE = bytes.fromhex("fa ce 76 a1 d0 cf")
OUTLINE_POST_SIGNATURE = bytes.fromhex("a2 00 00 8e")

CHAR_START_HOOK = bytes.fromhex("5c 80 71 ed")
FONT_ROW_HOOK = bytes.fromhex("22 00 71 ed")
CHAR_END_HOOK = bytes.fromhex("5c c0 70 ed ea ea")
OUTLINE_POST_HOOK = bytes.fromhex("5c 80 72 ed")
CHAR_START_HELPER = bytes.fromhex("22 b0 73 ed 90 4c 22 80 73 ed af 00 1d 00 10 27 da 8a 8d 86 93 af d4 a1 7e f0 1b c2 20 29 ff 00 ea aa e2 20 bf d7 a1 7e cd 86 93 f0 05 ca 10 f4 80 04 22 80 78 ed fa da c2 20 ad 82 93 29 f8 00 8d 86 93 4a 18 6d 86 93 a8 e2 20 fa bd 90 93 e8 80 04 bd a4 a1 e8 5c 8a 16 c0")
CHAR_END_HELPER = bytes.fromhex("fa 22 b0 73 ed 90 1f bd 8f 93 29 7f 8d 8a 93 9c 8b 93 da ae 8a 93 bf 00 72 ed fa 18 6d 82 93 8d 82 93 22 10 79 ed a9 00 ce 76 a1 f0 04 5c 86 16 c0 5c 40 73 ed")
FONT_ROW_HELPER = bytes.fromhex("22 b0 73 ed 90 05 22 60 45 c7 6b bf 00 dc d2 6b")
OUTLINE_POST_HELPER = bytes.fromhex("af 85 93 7e c9 01 d0 52 9c 8c 93 a2 00 00 a0 00 00 a9 0c 8d 8d 93 bd 00 90 89 80 f0 0d ad 8c 93 f0 08 b9 e4 93 09 01 99 e4 93 bd 00 90 89 01 f0 0f ad 8c 93 c9 1f f0 08 b9 24 94 09 80 99 24 94 e8 c8 c8 ce 8d 93 d0 ce c8 c8 c8 c8 c8 c8 c8 c8 ee 8c 93 ad 8c 93 c9 20 d0 b7 a2 00 00 8e 91 a1 8e 73 a1 ee 5d a1 5c 74 11 c0")
CHUNK_COMMIT_HELPER = bytes.fromhex("22 b0 73 ed 90 22 ad 8e 93 c9 27 b0 1b ad ce a1 10 07 ad 8e 93 c9 21 90 0f 22 80 73 ed ad ce a1 29 80 0d 8f 93 8d ce a1 a9 00 5c b7 16 c0")
CHUNK_CELLS_SNAPSHOT_HELPER = bytes.fromhex("8a cd 8e 93 d0 24 ad 82 93 d0 09 ad 8e 93 f0 17 a9 20 80 13 29 07 f0 09 ad 82 93 4a 4a 4a 1a 80 06 ad 82 93 4a 4a 4a 8d 8f 93 6b")
EVENT_RENDER_SCOPE_HELPER = bytes.fromhex("ad 85 93 f0 02 38 6b 18 6b")
CHOICE_VISUAL_HELPER = bytes.fromhex("ad d4 a1 c9 02 d0 71 da ae d9 a1 bd 90 93 fa c9 cc d0 05 9c c0 93 80 60 e0 00 00 f0 0c e0 01 00 f0 22 e0 02 00 f0 38 80 4f ad 86 93 c9 03 b0 02 a9 03 3a 3a 8d bd 93 0a 0a 0a 8d 82 93 9c bc 93 9c c0 93 6b ad bc 93 18 69 07 b0 2c 29 f8 c9 88 b0 03 18 69 08 8d 82 93 4a 4a 4a 8d be 93 6b ad bc 93 18 69 07 b0 11 29 f8 8d 82 93 4a 4a 4a 8d bf 93 a9 01 8d c0 93 6b ad 86 93 0a 0a 0a 8d 82 93 6b")
CHOICE_TRACKER_HELPER = bytes.fromhex("af 00 1d 00 10 14 ad d4 a1 c9 02 d0 0d bd 8f 93 c9 80 f0 06 ad 82 93 8d bc 93 6b")

def validate_stock(base: bytes) -> None:
    for off, sig, label in (
        (CHAR_START_FILE, CHAR_START_SIGNATURE, "character start"),
        (FONT_ROW_FILE, FONT_ROW_SIGNATURE, "font row"),
        (CHAR_END_FILE, CHAR_END_SIGNATURE, "character end"),
        (OUTLINE_POST_FILE, OUTLINE_POST_SIGNATURE, "post-outline"),
    ):
        if base[off:off+len(sig)] != sig:
            raise SystemExit(f"Unexpected clean-US shared VWF {label} signature")

def install(rom: bytearray, width_table: bytes) -> None:
    if len(width_table) != 128:
        raise ValueError("shared VWF runtime width table must contain 128 bytes")
    rom[CHAR_START_FILE:CHAR_START_FILE+len(CHAR_START_HOOK)] = CHAR_START_HOOK
    rom[FONT_ROW_FILE:FONT_ROW_FILE+len(FONT_ROW_HOOK)] = FONT_ROW_HOOK
    rom[CHAR_END_FILE:CHAR_END_FILE+len(CHAR_END_HOOK)] = CHAR_END_HOOK
    rom[OUTLINE_POST_FILE:OUTLINE_POST_FILE+len(OUTLINE_POST_HOOK)] = OUTLINE_POST_HOOK
    for off, payload in (
        (CHAR_START_HELPER_FILE, CHAR_START_HELPER),
        (CHAR_END_HELPER_FILE, CHAR_END_HELPER),
        (FONT_ROW_HELPER_FILE, FONT_ROW_HELPER),
        (WIDTH_TABLE_FILE, width_table),
        (OUTLINE_POST_HELPER_FILE, OUTLINE_POST_HELPER),
        (CHUNK_COMMIT_HELPER_FILE, CHUNK_COMMIT_HELPER),
        (CHUNK_CELLS_SNAPSHOT_FILE, CHUNK_CELLS_SNAPSHOT_HELPER),
        (EVENT_RENDER_SCOPE_HELPER_FILE, EVENT_RENDER_SCOPE_HELPER),
        (CHOICE_VISUAL_HELPER_FILE, CHOICE_VISUAL_HELPER),
        (CHOICE_TRACKER_HELPER_FILE, CHOICE_TRACKER_HELPER),
    ):
        rom[off:off+len(payload)] = payload
