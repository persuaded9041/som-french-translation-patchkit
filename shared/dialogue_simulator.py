"""Independent dialogue-box simulator for component 06/08 output.

The formatter decides where it *wants* lines/pages to break.  This simulator is
intentionally downstream of that decision: it serializes the final event bytes,
decodes those bytes with the dialogue $E8 direct/DTE boundary, expands dynamic
PLAYER_NAME commands, and applies the validated component-06 glyph metrics and
runtime limits again.

It is not a CPU emulator.  Event commands unrelated to text are preserved as
annotations, and unsupported text-layout commands are reported instead of being
guessed.  For ordinary dialogue it models the failure modes that matter to the
current formatter: 38 decoded glyphs, VWF visible-pixel preflight, safe-space
rewind, explicit line breaks, WAIT/TEXT_CLEAR page transitions, and the three
physical lines of a dialogue page.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from shared.dialogue_codec import COMMAND_LENGTHS, COMMAND_NAMES, serialize_event
from shared.french_charset import DIALOGUE_FRENCH_CHARS, glyph_bytes
from shared.stock_text import CODE_TO_TEXT, DTE_TABLE_FILE, TEXT_TO_CODE
from shared.vwf_geometry import ink_bounds
from shared.vwf_metrics import apply_validated_framing, validated_advance

FONT_BASE = 0x12DC00
FONT_ROWS = 12
GLYPH_COUNT = 128
DIALOGUE_DTE_THRESHOLD = 0xE8
RUNTIME_MAX_DECODED = 38
RUNTIME_BITMAP_PIXELS = 256
FORMATTER_TARGET_PIXELS = 240
PAGE_LINES = 3

STRUCTURAL_GLYPH_TEXT = {
    0xCE: "▽",  # validated choice/question marker
    0xCF: "←",
    0xD0: "→",
}


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    event_id: str
    box: int | None = None
    page: int | None = None
    line: int | None = None


@dataclass
class Glyph:
    code: int
    char: str
    dynamic_name: bool = False
    player_index: int | None = None
    layout_padding: bool = False


@dataclass
class SimLine:
    glyphs: list[Glyph] = field(default_factory=list)
    break_kind: str = "event_end"
    implicit_wrap: bool = False
    advance_pixels: int = 0
    visible_extent_pixels: int = 0
    decoded_count: int = 0
    parser_units: int = 0
    dynamic_name_blocks: int = 0

    @property
    def text(self) -> str:
        return "".join(g.char for g in self.glyphs)


@dataclass
class SimPage:
    lines: list[SimLine] = field(default_factory=list)
    waits: list[str] = field(default_factory=list)
    transition: str = ""


@dataclass
class SimBox:
    pages: list[SimPage] = field(default_factory=list)
    implicit_open: bool = False


@dataclass
class EventSimulation:
    event_id: str
    boxes: list[SimBox]
    issues: list[Issue]
    encoded: bytes
    translated_ids: list[str]

    @property
    def status(self) -> str:
        if any(issue.severity == "error" for issue in self.issues):
            return "error"
        if any(issue.severity == "warning" for issue in self.issues):
            return "warning"
        return "ok"


@dataclass(frozen=True)
class DialogueFont:
    rows: dict[int, bytes]
    advances: dict[int, int]
    right_edges: dict[int, int]


def make_dialogue_font(base_rom: bytes) -> DialogueFont:
    font = bytearray(base_rom[FONT_BASE:FONT_BASE + GLYPH_COUNT * FONT_ROWS])
    if len(font) != GLYPH_COUNT * FONT_ROWS:
        raise ValueError("Reference ROM is too small for the stock dialogue font")

    # Component 06/08 installs the complete dialogue profile at D3-E7.
    first_code = min(TEXT_TO_CODE[ch] for ch in DIALOGUE_FRENCH_CHARS)
    replacement = glyph_bytes(DIALOGUE_FRENCH_CHARS)
    start = (first_code - 0x80) * FONT_ROWS
    font[start:start + len(replacement)] = replacement

    rows_by_code: dict[int, bytes] = {}
    advances: dict[int, int] = {}
    right_edges: dict[int, int] = {}
    for code in range(0x80, 0x100):
        raw = bytes(font[(code - 0x80) * FONT_ROWS:(code - 0x80 + 1) * FONT_ROWS])
        framed = apply_validated_framing(code, raw)
        rows_by_code[code] = framed
        advances[code] = validated_advance(code, raw)
        bounds = ink_bounds(framed)
        right_edges[code] = -1 if bounds is None else bounds[1]
    return DialogueFont(rows_by_code, advances, right_edges)


def _dte_pair(base_rom: bytes, code: int) -> tuple[int, int]:
    if 0x60 <= code <= 0x7C:
        pair_index = code - 0x60
    elif DIALOGUE_DTE_THRESHOLD <= code <= 0xFF:
        # Component 06 keeps the stock upper-DTE addressing basis ($C3), only
        # the direct/DTE threshold changes from E6 to E8 in real dialogue.
        pair_index = code - 0xC3
    else:
        raise ValueError(f"Not a dialogue DTE source byte: ${code:02X}")
    pair = base_rom[DTE_TABLE_FILE + pair_index * 2:DTE_TABLE_FILE + pair_index * 2 + 2]
    if len(pair) != 2:
        raise ValueError(f"Truncated DTE pair for ${code:02X}")
    return pair[0], pair[1]


def _command_length(data: bytes, pos: int) -> int:
    opcode = data[pos]
    if opcode == 0x2D:
        if pos + 1 >= len(data):
            raise ValueError("truncated $2D command")
        return 4 if data[pos + 1] in (0x05, 0x06) else 2
    try:
        return COMMAND_LENGTHS[opcode]
    except KeyError as exc:
        raise ValueError(f"unsupported event opcode ${opcode:02X}") from exc


def _glyph_char(code: int) -> str:
    if code in STRUCTURAL_GLYPH_TEXT:
        return STRUCTURAL_GLYPH_TEXT[code]
    return CODE_TO_TEXT.get(code, f"‹{code:02X}›")


class _Simulator:
    def __init__(
        self,
        *,
        event_id: str,
        base_rom: bytes,
        font: DialogueFont,
        player_names: dict[int, str],
        translated_ids: list[str],
    ) -> None:
        self.event_id = event_id
        self.base_rom = base_rom
        self.font = font
        self.player_names = player_names
        self.translated_ids = translated_ids
        self.boxes: list[SimBox] = []
        self.issues: list[Issue] = []
        self.box: SimBox | None = None
        self.line_glyphs: list[Glyph] = []
        self.visible_lines: list[SimLine] = []
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.changed_since_snapshot = False
        self.last_safe_split: int | None = None
        self.line_control_epoch = 0
        self.line_dynamic_blocks = 0
        self.last_wait: str | None = None

    def issue(self, severity: str, code: str, message: str, *, line: int | None = None) -> None:
        self.issues.append(
            Issue(
                severity=severity,
                code=code,
                message=message,
                event_id=self.event_id,
                box=len(self.boxes) if self.box is not None else None,
                page=(len(self.box.pages) + 1 if self.box is not None else None),
                line=line,
            )
        )

    def ensure_box(self, *, implicit: bool = False) -> None:
        if self.box is not None:
            return
        self.box = SimBox(implicit_open=implicit)
        self.boxes.append(self.box)
        self.visible_lines = []
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.changed_since_snapshot = False
        self.last_wait = None
        if implicit:
            self.issue("info", "IMPLICIT_TEXT_BOX", "Text begins without TEXT_OPEN; preview assumes the box is already open.")

    def _line_metrics(self, glyphs: list[Glyph] | None = None) -> tuple[int, int, int, int, int]:
        glyphs = self.line_glyphs if glyphs is None else glyphs
        cursor = 0
        visible = 0
        dynamic_keys: list[tuple[int | None, int]] = []
        in_dynamic = False
        previous_index: int | None = None
        for glyph in glyphs:
            edge = self.font.right_edges[glyph.code]
            if edge >= 0:
                visible = max(visible, cursor + edge + 1)
            cursor += self.font.advances[glyph.code]
            if glyph.dynamic_name:
                key = glyph.player_index
                if not in_dynamic or key != previous_index:
                    dynamic_keys.append((key, len(dynamic_keys)))
                in_dynamic = True
                previous_index = key
            else:
                in_dynamic = False
                previous_index = None
        decoded = len(glyphs)
        dynamic_blocks = len(dynamic_keys)
        # Runtime batch-1 evidence: reserve one parser unit per PLAYER_NAME
        # source switch even though the visible decoded count is unchanged.
        parser_units = decoded + dynamic_blocks
        return cursor, visible, decoded, parser_units, dynamic_blocks

    def _fits_runtime(self, glyphs: list[Glyph]) -> tuple[bool, str]:
        _, visible, decoded, _, _ = self._line_metrics(glyphs)
        if decoded > RUNTIME_MAX_DECODED:
            return False, "decoded_capacity"
        if visible > RUNTIME_BITMAP_PIXELS:
            return False, "visible_pixels"
        return True, ""

    def _reset_checkpoint(self) -> None:
        self.last_safe_split = None
        self.line_control_epoch += 1

    def _append_without_wrap(self, glyph: Glyph) -> None:
        # A source space is a safe rewind checkpoint only in ordinary event
        # text. Dynamic PLAYER_NAME bytes are a temporary source and are never
        # rewound by component 06.
        if (
            glyph.char == " "
            and not glyph.dynamic_name
            and not glyph.layout_padding
            and self.line_glyphs
        ):
            self.last_safe_split = len(self.line_glyphs)
        self.line_glyphs.append(glyph)

    def add_glyph(self, glyph: Glyph) -> None:
        self.ensure_box(implicit=True)
        candidate = self.line_glyphs + [glyph]
        fits, reason = self._fits_runtime(candidate)
        if fits or glyph.dynamic_name:
            if not fits and glyph.dynamic_name:
                self.issue(
                    "error",
                    "DYNAMIC_NAME_RUNTIME_OVERFLOW",
                    f"PLAYER_NAME temporary source exceeds runtime {reason.replace('_', ' ')} and cannot be safely rewound.",
                )
            self._append_without_wrap(glyph)
            return

        # Match component 06's safe-space rewind: finish before the last source
        # space and carry the already-decoded following word to the next line.
        if self.last_safe_split is not None and self.last_safe_split > 0:
            before = self.line_glyphs[:self.last_safe_split]
            carry = self.line_glyphs[self.last_safe_split + 1:]
            self.line_glyphs = before
            self.finish_line("implicit_runtime_wrap", implicit=True)
            self.line_glyphs = []
            self.last_safe_split = None
            for carried in carry:
                self._append_without_wrap(carried)
            self.issue(
                "error",
                "IMPLICIT_RUNTIME_WRAP",
                f"Runtime would rewind to the last safe space because of {reason.replace('_', ' ')}.",
            )
            self.add_glyph(glyph)
            return

        # No safe source-space checkpoint: hard break before the offending
        # glyph, as the parser preflight does.
        self.finish_line("implicit_hard_wrap", implicit=True)
        self.issue(
            "error",
            "IMPLICIT_RUNTIME_HARD_WRAP",
            f"Runtime would hard-break before a glyph because of {reason.replace('_', ' ')}.",
        )
        self.add_glyph(glyph)

    def add_dte(self, codes: tuple[int, int]) -> None:
        # DTE source bytes are atomic in the preflight. Test the complete pair
        # before committing it; current event dialogue contains no stock DTEs,
        # but this keeps the simulator faithful for future resources.
        glyphs = [Glyph(code, _glyph_char(code)) for code in codes]
        candidate = self.line_glyphs + glyphs
        fits, reason = self._fits_runtime(candidate)
        if fits:
            for glyph in glyphs:
                self._append_without_wrap(glyph)
            if glyphs[1].char == " " and len(self.line_glyphs) >= 2:
                self.last_safe_split = len(self.line_glyphs) - 1
            return
        if self.last_safe_split is not None and self.last_safe_split > 0:
            before = self.line_glyphs[:self.last_safe_split]
            carry = self.line_glyphs[self.last_safe_split + 1:]
            self.line_glyphs = before
            self.finish_line("implicit_runtime_wrap", implicit=True)
            self.line_glyphs = []
            self.last_safe_split = None
            for carried in carry:
                self._append_without_wrap(carried)
            self.issue("error", "IMPLICIT_RUNTIME_WRAP", f"Runtime would wrap before an atomic DTE pair because of {reason.replace('_', ' ')}.")
            self.add_dte(codes)
            return
        self.finish_line("implicit_hard_wrap", implicit=True)
        self.issue("error", "IMPLICIT_RUNTIME_HARD_WRAP", f"Runtime would hard-break before an atomic DTE pair because of {reason.replace('_', ' ')}.")
        self.add_dte(codes)

    def finish_line(self, kind: str, *, implicit: bool = False, allow_empty: bool = False) -> None:
        if not self.line_glyphs and not allow_empty:
            self.last_safe_split = None
            return
        self.ensure_box(implicit=True)
        advance, visible, decoded, parser_units, dynamic_blocks = self._line_metrics()
        line = SimLine(
            glyphs=list(self.line_glyphs),
            break_kind=kind,
            implicit_wrap=implicit,
            advance_pixels=advance,
            visible_extent_pixels=visible,
            decoded_count=decoded,
            parser_units=parser_units,
            dynamic_name_blocks=dynamic_blocks,
        )
        self.visible_lines.append(line)
        if len(self.visible_lines) > PAGE_LINES:
            self.visible_lines.pop(0)
        self.line_advances_since_pause += 1
        if self.line_glyphs:
            self.content_lines_since_pause += 1
        self.changed_since_snapshot = True
        line_no = min(PAGE_LINES, len(self.visible_lines))
        if parser_units > RUNTIME_MAX_DECODED:
            self.issue("error", "PARSER_SAFETY_EXCEEDED", f"Line uses {parser_units} conservative parser units (> {RUNTIME_MAX_DECODED}).", line=line_no)
        if visible > RUNTIME_BITMAP_PIXELS:
            self.issue("error", "VISIBLE_BITMAP_OVERFLOW", f"Visible ink reaches {visible}px (> {RUNTIME_BITMAP_PIXELS}px runtime bitmap).", line=line_no)
        if advance > FORMATTER_TARGET_PIXELS:
            self.issue("warning", "FORMATTER_PIXEL_TARGET_EXCEEDED", f"Line advance is {advance}px (> {FORMATTER_TARGET_PIXELS}px formatter target).", line=line_no)
        if self.content_lines_since_pause > PAGE_LINES:
            self.issue(
                "error",
                "UNPAUSED_SCROLL",
                f"{self.content_lines_since_pause} non-empty text lines were rendered since the previous WAIT/box opening; the first new line would scroll away before the player can pause.",
                line=line_no,
            )
        self.line_glyphs.clear()
        self.last_safe_split = None
        self.line_dynamic_blocks = 0

    def _snapshot(self, transition: str, *, wait: str | None = None, force: bool = False) -> None:
        self.ensure_box(implicit=True)
        assert self.box is not None
        if not force and not self.changed_since_snapshot and self.box.pages:
            if transition and self.box.pages[-1].transition == "":
                self.box.pages[-1].transition = transition
            if wait and wait not in self.box.pages[-1].waits:
                self.box.pages[-1].waits.append(wait)
            return
        page = SimPage(lines=list(self.visible_lines), transition=transition)
        if wait:
            page.waits.append(wait)
        self.box.pages.append(page)
        self.changed_since_snapshot = False

    def text_open(self) -> None:
        if self.box is not None:
            self.close_box("TEXT_OPEN restarted an active box")
        self.box = SimBox(implicit_open=False)
        self.boxes.append(self.box)
        self.visible_lines = []
        self.line_glyphs.clear()
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.changed_since_snapshot = False
        self.last_safe_split = None
        self.last_wait = None

    def page_clear(self) -> None:
        self.finish_line("text_clear")
        self.ensure_box(implicit=True)
        assert self.box is not None
        if self.last_wait == "WAIT $00" and self.box.pages:
            self.box.pages[-1].transition = "WAIT $00 + TEXT_CLEAR"
        elif self.changed_since_snapshot:
            self._snapshot("TEXT_CLEAR")
        self.visible_lines = []
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.changed_since_snapshot = False
        self.last_wait = None
        self._reset_checkpoint()

    def close_box(self, transition: str = "TEXT_CLOSE") -> None:
        if self.box is None:
            return
        self.finish_line(transition)
        if self.changed_since_snapshot or not self.box.pages:
            self._snapshot(transition, force=not self.box.pages)
        elif self.box.pages and not self.box.pages[-1].transition:
            self.box.pages[-1].transition = transition
        self.box = None
        self.visible_lines = []
        self.line_glyphs.clear()
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.changed_since_snapshot = False
        self.last_safe_split = None
        self.last_wait = None

    def add_wait(self, arg: int) -> None:
        # WAIT occurs after the current decoded chunk; finalize its last line,
        # snapshot the three-line rolling window, and only then let later text
        # scroll. This matches the stock scripts where WAIT alone separates
        # readable dialogue chunks without clearing the box.
        self.finish_line("wait")
        self.ensure_box(implicit=True)
        wait = f"WAIT ${arg:02X}"
        self._snapshot(wait, wait=wait, force=not (self.box and self.box.pages))
        self.line_advances_since_pause = 0
        self.content_lines_since_pause = 0
        self.last_wait = wait
        self._reset_checkpoint()

    def add_player_name(self, index: int) -> None:
        self.ensure_box(implicit=True)
        name = self.player_names.get(index, self.player_names.get(0, "000000000"))
        self._reset_checkpoint()
        try:
            codes = [TEXT_TO_CODE[char] for char in name]
        except KeyError as exc:
            self.issue("error", "PLAYER_NAME_UNENCODABLE", f"Simulator player name contains unsupported character {exc.args[0]!r}.")
            return
        for code, char in zip(codes, name):
            self.add_glyph(Glyph(code, char, dynamic_name=True, player_index=index))
        self._reset_checkpoint()

    def add_text_x(self, position: int) -> None:
        """Model the validated component-06 line-start TEXT_X behavior.

        Stock command $59 writes its argument to both the decoded-text count
        and text X position. On a fresh line the private decoded buffer is
        already padded with $80, so component 06 renders exactly ``position``
        leading space glyphs before the following text. Mid-line TEXT_X is an
        absolute cursor/count reset and remains deliberately unsupported.
        """
        self.ensure_box(implicit=True)
        if self.line_glyphs:
            self.unsupported_layout("TEXT_X", bytes([position]))
            return
        if position > RUNTIME_MAX_DECODED:
            self.issue(
                "error",
                "TEXT_X_RUNTIME_OVERFLOW",
                f"TEXT_X ${position:02X} exceeds the {RUNTIME_MAX_DECODED}-glyph decoded-line capacity.",
            )
            self._reset_checkpoint()
            return
        self._reset_checkpoint()
        for _ in range(position):
            self._append_without_wrap(Glyph(TEXT_TO_CODE[" "], " ", layout_padding=True))
        self._reset_checkpoint()

    def unsupported_layout(self, name: str, args: bytes) -> None:
        self.issue("error", "UNSUPPORTED_LAYOUT_COMMAND", f"Simulator does not yet model {name} {args.hex(' ').upper()}; event must remain review-only.")
        self._reset_checkpoint()

    def run(self, data: bytes) -> EventSimulation:
        pos = 0
        while pos < len(data):
            opcode = data[pos]

            if opcode == 0x7D:
                # Ending-text mode is not ordinary component-06 dialogue.
                end = data.find(b"\x7E", pos + 1)
                if end < 0:
                    self.issue("error", "UNTERMINATED_ENDING_TEXT", "Unterminated $7D ending-text block.")
                    break
                self.issue("warning", "ENDING_TEXT_UNSIMULATED", "Special ending-text mode is outside the ordinary dialogue simulator.")
                pos = end + 1
                continue

            if opcode == 0x7F:
                self.finish_line("explicit_newline", allow_empty=True)
                pos += 1
                continue

            if 0x80 <= opcode < DIALOGUE_DTE_THRESHOLD:
                self.add_glyph(Glyph(opcode, _glyph_char(opcode)))
                pos += 1
                continue

            if 0x60 <= opcode <= 0x7C or opcode >= DIALOGUE_DTE_THRESHOLD:
                pair = _dte_pair(self.base_rom, opcode)
                if any(code < 0x80 for code in pair):
                    self.issue("error", "DTE_NON_GLYPH", f"DTE ${opcode:02X} expands outside direct glyph range: {pair!r}.")
                else:
                    self.add_dte(pair)
                pos += 1
                continue

            try:
                length = _command_length(data, pos)
            except ValueError as exc:
                self.issue("error", "UNKNOWN_COMMAND", str(exc))
                break
            if pos + length > len(data):
                self.issue("error", "TRUNCATED_COMMAND", f"Truncated command ${opcode:02X} at +${pos:04X}.")
                break
            raw = data[pos:pos + length]
            args = raw[1:]
            name = COMMAND_NAMES.get(opcode, f"OP_{opcode:02X}")

            if name == "TEXT_OPEN":
                self.text_open()
            elif name == "TEXT_CLOSE":
                self.close_box("TEXT_CLOSE")
            elif name == "TEXT_CLEAR":
                self.page_clear()
            elif name == "WAIT":
                self.add_wait(args[0] if args else 0)
            elif name == "PLAYER_NAME":
                self.add_player_name(args[0] if args else 0)
            elif name == "TEXT_X":
                self.add_text_x(args[0] if args else 0)
            elif name in {"ENEMY_NAME", "WEAPON_NAME", "MAGIC_NAME", "TEXT_LIST_VALUE"}:
                self.unsupported_layout(name, args)
            elif name == "MONEY_PRINT":
                # MONEY_PRINT updates the separate money display rather than
                # appending glyphs to the component-06 dialogue buffer. Event
                # $01CF executes it before TEXT_OPEN, proving it is outside the
                # ordinary dialogue text stream. Keep it as a control boundary
                # for word-rewind purposes, but consume no dialogue geometry.
                self._reset_checkpoint()
            elif name in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}:
                # Choice geometry needs a dedicated model. Do not guess.
                self.unsupported_layout(name, args)
            elif name == "END":
                self.close_box("END")
            else:
                # Ordinary event commands can safely be ignored visually, but
                # they form a source/control boundary for word-rewind purposes.
                self._reset_checkpoint()
            pos += length

        self.close_box("event_end")
        return EventSimulation(
            event_id=self.event_id,
            boxes=self.boxes,
            issues=self.issues,
            encoded=data,
            translated_ids=self.translated_ids,
        )


def simulate_event(
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    *,
    font: DialogueFont | None = None,
    player_names: dict[int, str] | None = None,
) -> EventSimulation:
    font = font or make_dialogue_font(base_rom)
    player_names = player_names or {0: "000000000", 1: "000000000", 2: "000000000"}
    translated_ids = [
        token["id"]
        for token in event["tokens"]
        if token.get("type") in {"text", "ending_text"} and token.get("id") in translations
    ]
    data = serialize_event(base_rom, event, translations=translations, source=False)
    return _Simulator(
        event_id=event["event_id"],
        base_rom=base_rom,
        font=font,
        player_names=player_names,
        translated_ids=translated_ids,
    ).run(data)
