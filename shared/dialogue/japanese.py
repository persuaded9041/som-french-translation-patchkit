"""Read original Japanese dialogue events from the clean Seiken Densetsu 2 ROM.

This module is analysis-only.  It deliberately does not participate in patch
building or Android identity.  Its useful bridge is the stable USA carrier ID
(``C9:916F`` etc.): the canonical USA asset identifies the owning event, then
that same event ID is read from the Japanese ROM and decoded with the original
SFC text compression.

The Japanese event format uses the same event pointer tables/command stream as
the western ROMs, but its text codec is different.  Direct bytes $80-$FF index
the default table.  Prefixes $60-$67, $68-$6B and $6C-$6F encode 1-8 / 1-4 /
1-4 characters through the S1/S2/S3 shifted tables.  $7F is a newline.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Iterable

from shared.dialogue.codec import COMMAND_LENGTHS, COMMAND_NAMES
from shared.text.ids import rom_text_id

JP_ROM_SIZE = 0x200000
JP_ROM_SHA256 = "7fd1747eb4333f502d5fe6df7267342e4b4a399ab65b57f0a139e5f9fc02ab9d"

C9_BASE = 0x090000
CA_BASE = 0x0A0000
C9_EVENT_COUNT = 0x400
EVENT_COUNT = 0x800
C9_LAST_EVENT_ID = 0x03FF

# Four 128-entry glyph pages recovered for the original SFC dialogue codec.
# The shifted lookup overlaps adjacent pages:
#   S1: DEFAULT[00-7F] + PAGE_B[80-FF]
#   S2: PAGE_B[00-7F]  + PAGE_C[80-FF]
#   S3: PAGE_C[00-7F]  + PAGE_D[80-FF]
DEFAULT_TABLE = tuple(
    list("、。！？ー‥「」『』")
    + list("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわんをっゃゅょぁぃぅぇぉ")
    + list("がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ")
    + list("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ")
    + list("・：；～／（）")
    + list("聖剣伝説")
    + ["　"]
)
PAGE_B = tuple(
    list("０１２３４５６７８９")
    + list("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワンヲッャュョァィゥェォ")
    + list("ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ")
    + list("ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ")
    + list("ヴ々落悪入手用先安誰音▽")
)
PAGE_C = tuple(
    list("主人町森来間思合光消形回困長老東西歴史会関係真北南大地石目何林通男後店娘女供帝国私客化行方明皇要塞雨木滅君％生血佐守戦争騎士敵穴向引邪動成功夫文若流失水外自身本弱")
    + list("失械賢者海島話世界全死好災古代岩宝父年殿草高強切仲系白毒酸物復点眠宇宙陸少山指滝事当")
    + ["MP", "↑", "↓", "←", "→"]
)
PAGE_D = tuple(
    list("押以城字十決選定時左右進次戻魔見法力人器避武変各攻始撃消回終防御屋一現最初同上下技面共旅鳴平精和知体氷船中神命前小多世作続界獣金機接近待名勇気愛恵心砂漠底昔振起刀火炎竜天黄胸使闇道着革王冠霊羽母抜出村子砲爆弾針杯薬風太鼓種箱味裏丸月輪銀矢弓鉄能巨妖修封印聞")
)

for _name, _table in (
    ("DEFAULT_TABLE", DEFAULT_TABLE),
    ("PAGE_B", PAGE_B),
    ("PAGE_C", PAGE_C),
    ("PAGE_D", PAGE_D),
):
    if len(_table) != 0x80:  # pragma: no cover - import-time invariant
        raise AssertionError(f"{_name} must contain exactly 128 entries, got {len(_table)}")


@dataclass(frozen=True)
class JapaneseTextToken:
    text: str
    raw: bytes
    file_offset: int

    @property
    def id(self) -> str:
        return rom_text_id(self.file_offset)


@dataclass(frozen=True)
class CarrierExtraction:
    us_carrier: str
    event_id: int
    us_text: str
    match_kind: str
    japanese_matches: tuple[JapaneseTextToken, ...]
    japanese_text_tokens: tuple[JapaneseTextToken, ...]
    note: str


def validate_japanese_rom(data: bytes) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != JP_ROM_SIZE or digest != JP_ROM_SHA256:
        raise ValueError(
            "Wrong Japanese ROM. Expected clean unheadered Seiken Densetsu 2 (Japan) "
            f"({JP_ROM_SIZE:#x} bytes, SHA-256 {JP_ROM_SHA256}); got "
            f"{len(data):#x} bytes, SHA-256 {digest}."
        )


def normalize_carrier_id(value: str) -> str:
    value = value.strip().upper()
    if value.startswith("$"):
        value = value[1:]
    if len(value) != 7 or value[2] != ":":
        raise ValueError("carrier ID must look like C9:916F or CA:6629")
    bank, addr = value.split(":", 1)
    if bank not in {"C9", "CA"}:
        raise ValueError("dialogue carrier bank must be C9 or CA")
    try:
        int(addr, 16)
    except ValueError as exc:
        raise ValueError("carrier address must be hexadecimal") from exc
    return value


def _event_span(rom: bytes, event_id: int) -> tuple[int, int, int]:
    """Return Japanese event ``(file_start, length, pointer)``.

    Event $03FF has no following C9 pointer and is deliberately rejected rather
    than guessed.  All other stock events have a usable following table entry.
    """
    if not 0 <= event_id < EVENT_COUNT:
        raise ValueError(f"event ID out of range: ${event_id:04X}")
    if event_id == C9_LAST_EVENT_ID:
        raise ValueError(
            "Japanese event $03FF has no C9 sentinel; its physical end is not "
            "established by this analysis tool"
        )
    if event_id < C9_EVENT_COUNT:
        base = C9_BASE
        index = event_id
    else:
        base = CA_BASE
        index = event_id - C9_EVENT_COUNT
    table = base + index * 2
    pointer = struct.unpack_from("<H", rom, table)[0]
    next_pointer = struct.unpack_from("<H", rom, table + 2)[0]
    if next_pointer <= pointer:
        raise ValueError(
            f"Japanese event ${event_id:04X} has non-forward pointers "
            f"${pointer:04X} -> ${next_pointer:04X}"
        )
    return base + pointer, next_pointer - pointer, pointer


def _shift_lookup(shift: int, value: int) -> str:
    if shift == 1:
        return DEFAULT_TABLE[value] if value < 0x80 else PAGE_B[value - 0x80]
    if shift == 2:
        return PAGE_B[value] if value < 0x80 else PAGE_C[value - 0x80]
    if shift == 3:
        return PAGE_C[value] if value < 0x80 else PAGE_D[value - 0x80]
    raise ValueError(f"invalid Japanese text shift S{shift}")



def _decode_text_unit(data: bytes, pos: int) -> tuple[str, int] | None:
    value = data[pos]
    if value >= 0x80:
        return DEFAULT_TABLE[value - 0x80], 1
    if 0x60 <= value <= 0x67:
        shift, count = 1, value - 0x60 + 1
    elif 0x68 <= value <= 0x6B:
        shift, count = 2, value - 0x68 + 1
    elif 0x6C <= value <= 0x6F:
        shift, count = 3, value - 0x6C + 1
    elif value == 0x7F:
        return "\n", 1
    else:
        return None
    end = pos + 1 + count
    if end > len(data):
        raise ValueError(f"truncated Japanese S{shift} text run at +${pos:04X}")
    return "".join(_shift_lookup(shift, item) for item in data[pos + 1 : end]), 1 + count


def _command_length(data: bytes, pos: int) -> int:
    opcode = data[pos]
    if opcode == 0x2D:
        if pos + 1 >= len(data):
            raise ValueError("truncated $2D effect command")
        return 4 if data[pos + 1] in (0x05, 0x06) else 2
    try:
        return COMMAND_LENGTHS[opcode]
    except KeyError as exc:
        raise ValueError(f"unsupported Japanese event opcode ${opcode:02X}") from exc


def parse_japanese_event(rom: bytes, event_id: int) -> dict[str, Any]:
    """Parse one Japanese event into command/text tokens.

    Unknown structures fail instead of being interpreted as prose.  ``$7D...$7E``
    ending-text blocks are retained as raw blocks because that western special
    renderer is outside the scope of this dialogue extraction helper.
    """
    start, size, pointer = _event_span(rom, event_id)
    data = rom[start : start + size]
    tokens: list[dict[str, Any]] = []
    pos = 0
    while pos < len(data):
        decoded = _decode_text_unit(data, pos)
        if decoded is not None:
            text_start = pos
            parts: list[str] = []
            while pos < len(data):
                piece = _decode_text_unit(data, pos)
                if piece is None:
                    break
                text, consumed = piece
                parts.append(text)
                pos += consumed
            raw = bytes(data[text_start:pos])
            token = JapaneseTextToken("".join(parts), raw, start + text_start)
            tokens.append(
                {
                    "type": "text",
                    "id": token.id,
                    "source": token.text,
                    "raw": token.raw,
                    "file_offset": token.file_offset,
                }
            )
            continue

        opcode = data[pos]
        if opcode == 0x7D:
            end = data.find(b"\x7E", pos + 1)
            if end < 0:
                raise ValueError(f"Japanese event ${event_id:04X}: unterminated $7D block")
            tokens.append(
                {
                    "type": "ending_text_raw",
                    "raw": bytes(data[pos : end + 1]),
                    "file_offset": start + pos,
                }
            )
            pos = end + 1
            continue

        length = _command_length(data, pos)
        if pos + length > len(data):
            raise ValueError(f"Japanese event ${event_id:04X}: truncated command at +${pos:04X}")
        raw = bytes(data[pos : pos + length])
        command: dict[str, Any] = {
            "type": "command",
            "name": COMMAND_NAMES.get(opcode, f"OP_{opcode:02X}"),
            "opcode": opcode,
        }
        if len(raw) > 1:
            command["args"] = raw[1:].hex(" ").upper()
        tokens.append(command)
        pos += length

    return {
        "event_id": f"{event_id:04X}",
        "jp_pointer": f"{pointer:04X}",
        "jp_file_start": start,
        "jp_event_start": rom_text_id(start),
        "tokens": tokens,
    }


def _load_source(source_path: Path) -> dict[str, Any]:
    doc = json.loads(source_path.read_text(encoding="utf-8"))
    if doc.get("format_version") not in (2, 3, 4):
        raise ValueError(f"unsupported dialogue source format in {source_path}")
    return doc


def _find_us_carrier(source: dict[str, Any], carrier_id: str) -> tuple[dict[str, Any], int, dict[str, Any]]:
    hits: list[tuple[dict[str, Any], int, dict[str, Any]]] = []
    for event in source.get("events", []):
        for index, token in enumerate(event.get("tokens", [])):
            if token.get("id") == carrier_id:
                hits.append((event, index, token))
    if not hits:
        raise ValueError(f"USA carrier {carrier_id} was not found in assets/dialogues.json")
    if len(hits) != 1:
        raise ValueError(f"USA carrier {carrier_id} is not unique in assets/dialogues.json")
    return hits[0]


def _token_kind(token: dict[str, Any]) -> str:
    return "text" if token.get("type") in {"text", "ending_text", "ending_text_raw"} else token.get("type", "")


def _command_name_sequence(tokens: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(token.get("name", "") for token in tokens if token.get("type") == "command")


def _text_tokens(parsed_event: dict[str, Any]) -> tuple[JapaneseTextToken, ...]:
    return tuple(
        JapaneseTextToken(token["source"], token["raw"], token["file_offset"])
        for token in parsed_event["tokens"]
        if token.get("type") == "text"
    )


def extract_for_us_carrier(
    rom: bytes,
    carrier_id: str,
    *,
    source_path: Path,
) -> CarrierExtraction:
    """Resolve a USA dialogue carrier to conservative Japanese event evidence."""
    carrier_id = normalize_carrier_id(carrier_id)
    source = _load_source(source_path)
    us_event, us_index, us_token = _find_us_carrier(source, carrier_id)
    event_id = int(us_event["event_id"], 16)
    jp_event = parse_japanese_event(rom, event_id)
    jp_texts = _text_tokens(jp_event)

    us_tokens = us_event["tokens"]
    jp_tokens = jp_event["tokens"]
    us_text_count = sum(_token_kind(t) == "text" for t in us_tokens)

    # Strongest case: token shape and every command (including args) are the
    # same.  Text itself may of course differ by language.
    exact_shape = len(us_tokens) == len(jp_tokens)
    if exact_shape:
        for us, jp in zip(us_tokens, jp_tokens):
            if _token_kind(us) != _token_kind(jp):
                exact_shape = False
                break
            if us.get("type") == "command":
                if us.get("name") != jp.get("name") or us.get("args", "") != jp.get("args", ""):
                    exact_shape = False
                    break
    if exact_shape and _token_kind(jp_tokens[us_index]) == "text":
        token = jp_tokens[us_index]
        match = JapaneseTextToken(token["source"], token["raw"], token["file_offset"])
        return CarrierExtraction(
            carrier_id,
            event_id,
            us_token.get("source", ""),
            "exact_event_structure",
            (match,),
            jp_texts,
            "Same event ID and identical command/token structure; carrier position is one-to-one.",
        )

    # Still strong enough for extraction when each version contains exactly
    # one text carrier.  This handles regional script changes such as a removed
    # PLAYER_NAME command without pretending the command streams are identical.
    if us_text_count == 1 and len(jp_texts) == 1:
        return CarrierExtraction(
            carrier_id,
            event_id,
            us_token.get("source", ""),
            "unique_text_in_event",
            jp_texts,
            jp_texts,
            "Both regional versions contain exactly one dialogue text block in this event.",
        )

    # If the token kinds and command names line up but coordinates/arguments
    # differ, the positional text carrier remains structurally identifiable.
    same_kind_shape = len(us_tokens) == len(jp_tokens) and all(
        _token_kind(us) == _token_kind(jp) for us, jp in zip(us_tokens, jp_tokens)
    )
    if same_kind_shape and _command_name_sequence(us_tokens) == _command_name_sequence(jp_tokens):
        if _token_kind(jp_tokens[us_index]) == "text":
            token = jp_tokens[us_index]
            match = JapaneseTextToken(token["source"], token["raw"], token["file_offset"])
            return CarrierExtraction(
                carrier_id,
                event_id,
                us_token.get("source", ""),
                "same_structure_command_args_differ",
                (match,),
                jp_texts,
                "Token layout and command names match; only regional command arguments differ.",
            )

    # Do not guess through resegmentation.  The complete Japanese event text is
    # returned so a human can inspect the source block (notably event $0278).
    return CarrierExtraction(
        carrier_id,
        event_id,
        us_token.get("source", ""),
        "resegmented_or_ambiguous",
        (),
        jp_texts,
        "No one-to-one Japanese carrier can be proven from event structure; inspect the Japanese event text blocks.",
    )


def extraction_to_json(result: CarrierExtraction) -> dict[str, Any]:
    def token_json(token: JapaneseTextToken) -> dict[str, Any]:
        return {
            "id": token.id,
            "file_offset": f"{token.file_offset:06X}",
            "raw_hex": token.raw.hex(" ").upper(),
            "text": token.text,
        }

    return {
        "us_carrier": result.us_carrier,
        "event_id": f"{result.event_id:04X}",
        "us_text": result.us_text,
        "match_kind": result.match_kind,
        "note": result.note,
        "japanese_matches": [token_json(token) for token in result.japanese_matches],
        "japanese_event_text": [token_json(token) for token in result.japanese_text_tokens],
    }
