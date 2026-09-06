"""Deterministic Android-French -> SNES dialogue formatting helpers.

Alignment and layout are intentionally separate.  This module accepts only an
already-established Android/SNES mapping and converts the localized prose into
existing SNES text-token slots. The normal path preserves every event command.
A separately gated extra-page path may insert only the stock WAIT $00 +
TEXT_CLEAR transition when a validated translation needs one additional page.

The first runtime checkpoint was deliberately narrow (event $0107); later
complete-event batches reuse the same binding and VWF primitives. The explicit
extra-page transition and sentence-aware boundary placement are runtime-validated
on $010F; later batches reuse that rule and prefer page boundaries after complete
sentences.
The offline formatter uses a conservative 240-pixel VWF target and also enforces
component 06's runtime-validated 38-decoded-character parser capacity. The renderer bitmap itself is 32 cells / 256 pixels; that physical
capacity is a separate runtime concern, not the only offline wrapping limit.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from shared.french_charset import DIALOGUE_FRENCH_CHARS, glyph_bytes
from shared.stock_text import TEXT_TO_CODE
from shared.vwf_metrics import validated_advance

FONT_BASE = 0x12DC00
FONT_GLYPH_COUNT = 128
FONT_ROWS = 12
DIALOGUE_WRAP_PIXELS = 240
DIALOGUE_WRAP_CHARS = 38
DIALOGUE_PAGE_LINES = 3
MAX_PLAYER_NAME_CHARS = 9
PLAYER_NAME_PARSER_SAFETY_UNITS = 1
TRANSLATION_CLEAR = "\v"

PLAYER_PLACEHOLDER_RE = re.compile(r"%S\((\d+),0\)")

# Formatting-only semantic boundaries inferred from the localized prose. They
# never rewrite words: they only mark places where a speaker/attribution should
# begin on a fresh physical line.
_STRONG_SENTENCE_END = r"(?:\.{3}|[.!?…])[”\"»')\]]*"
_SPEAKER_LABEL = (
    r"(?:%S\(\d+,0\)|[A-ZÀ-ÖØ-ÞŒ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]*)"
    r"(?:\s+[A-ZÀ-ÖØ-ÞŒ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]*){0,2}\s*:"
)
_SPEAKER_AFTER_SENTENCE_RE = re.compile(
    rf"(?P<end>{_STRONG_SENTENCE_END})\s+(?P<label>{_SPEAKER_LABEL})"
)
_ATTRIBUTION_AFTER_QUOTE_RE = re.compile(
    rf"(?P<end>{_STRONG_SENTENCE_END})\s+-\s+"
)
_PUNCTUATION_ATOM_RE = re.compile(r"^[!?;:,.…]+[”\"»')\]]*$")


@dataclass(frozen=True)
class TextSlot:
    text_id: str
    source: str


@dataclass(frozen=True)
class PlayerSlot:
    index: int


BindingSlot = TextSlot | PlayerSlot


def make_dialogue_advances(base: bytes) -> dict[str, int]:
    """Return validated VWF advances for every editable SNES text character."""
    font = bytearray(base[FONT_BASE:FONT_BASE + FONT_GLYPH_COUNT * FONT_ROWS])
    if len(font) != FONT_GLYPH_COUNT * FONT_ROWS:
        raise ValueError("Reference ROM is too small for the stock dialogue font")

    french = glyph_bytes(DIALOGUE_FRENCH_CHARS)
    french_first = min(TEXT_TO_CODE[ch] for ch in DIALOGUE_FRENCH_CHARS)
    french_start = (french_first - 0x80) * FONT_ROWS
    font[french_start:french_start + len(french)] = french

    by_code: dict[int, int] = {}
    for code in range(0x80, 0x100):
        rows = font[(code - 0x80) * FONT_ROWS:(code - 0x80 + 1) * FONT_ROWS]
        by_code[code] = validated_advance(code, rows)

    advances: dict[str, int] = {}
    for char, code in TEXT_TO_CODE.items():
        if 0x80 <= code <= 0xFF:
            advances[char] = by_code[code]
    return advances


def player_placeholder_width(advances: dict[str, int]) -> int:
    """Conservative width for a dynamic name after the validated 9-char patch."""
    # Names use the same direct glyph set as dialogue.  Use the maximum editable
    # glyph advance so wrapping remains safe for every possible 9-character name.
    max_advance = max(advances.values())
    return MAX_PLAYER_NAME_CHARS * max_advance


def _normalize_android_quotes(text: str) -> str:
    """Convert Android ASCII quotes to the two stock SNES quote glyphs.

    Android uses straight quotes as presentation punctuation, while the stock
    SNES dialogue font exposes distinct opening/closing quote characters.  The
    conversion is deterministic and alternates within each localized string;
    it never changes apostrophes.
    """
    out: list[str] = []
    opening = True
    for char in text:
        if char != '"':
            out.append(char)
            continue
        out.append("“" if opening else "”")
        opening = not opening
    return "".join(out)


def normalize_android_french(text: str) -> str:
    """Discard Android presentation whitespace without rewriting the prose.

    ``_`` and U+3000 are presentation/layout separators in the Android assets;
    they are not SNES glyphs. Android hard line breaks likewise belong to the
    source presentation and are reflowed against the validated SNES VWF.
    Straight Android quotes are rebound to the stock SNES opening/closing quote
    glyphs. Square brackets are presentation-only choice delimiters and map to
    the stock parentheses used by the SNES interface.
    """
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("_", " ").replace("\u3000", " ")
    text = text.replace("[", "(").replace("]", ")")
    text = _normalize_android_quotes(text)
    return " ".join(text.split())


def apply_semantic_layout_hints(text: str) -> tuple[str, list[str]]:
    """Insert deterministic hard-line hints without changing localized prose.

    Android sometimes flattens speaker changes or attribution lines into one
    string. A new capitalized ``Name :`` label immediately after a completed
    sentence is a new spoken turn and must start on a new SNES line. Likewise,
    a dash attribution after a completed quoted sentence starts on its own
    line. These are line hints only; pagination remains a separate decision.
    """
    hints: list[str] = []

    def speaker(match: re.Match[str]) -> str:
        hints.append("speaker_after_sentence")
        return f"{match.group('end')}\n{match.group('label')}"

    def attribution(match: re.Match[str]) -> str:
        hints.append("attribution_after_quote")
        return f"{match.group('end')}\n- "

    text = _SPEAKER_AFTER_SENTENCE_RE.sub(speaker, text)
    text = _ATTRIBUTION_AFTER_QUOTE_RE.sub(attribution, text)
    return text, hints


def placeholder_sequence(text: str) -> tuple[int, ...]:
    return tuple(int(match.group(1)) for match in PLAYER_PLACEHOLDER_RE.finditer(text))


def _wrap_atoms(text: str) -> list[str]:
    """Return unbreakable word atoms for one semantic line segment.

    French Android strings often store a space before ``! ? ; :``. Treat a
    standalone punctuation token as part of the preceding word so wrapping can
    never strand punctuation on a line by itself (``loin`` / ``!``). The space
    remains inside the atom and therefore still contributes its real VWF width.
    """
    atoms: list[str] = []
    for token in text.split():
        if atoms and _PUNCTUATION_ATOM_RE.fullmatch(token):
            atoms[-1] += " " + token
        else:
            atoms.append(token)
    return atoms


def _markup_width(text: str, advances: dict[str, int], placeholder_width: int) -> int:
    width = 0
    cursor = 0
    for match in PLAYER_PLACEHOLDER_RE.finditer(text):
        for char in text[cursor:match.start()]:
            try:
                width += advances[char]
            except KeyError as exc:
                raise ValueError(f"Unsupported editable dialogue character: {char!r}") from exc
        width += placeholder_width
        cursor = match.end()
    for char in text[cursor:]:
        try:
            width += advances[char]
        except KeyError as exc:
            raise ValueError(f"Unsupported editable dialogue character: {char!r}") from exc
    return width


def _markup_chars(text: str, placeholder_chars: int = MAX_PLAYER_NAME_CHARS) -> int:
    """Count decoded visible characters, expanding PLAYER_NAME conservatively."""
    count = 0
    cursor = 0
    for match in PLAYER_PLACEHOLDER_RE.finditer(text):
        count += len(text[cursor:match.start()])
        count += placeholder_chars
        cursor = match.end()
    count += len(text[cursor:])
    return count


def wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Word-wrap markup while preserving semantic hard-line hints.

    Ordinary spaces are wrap opportunities. Newlines inserted by
    :func:`apply_semantic_layout_hints` are mandatory line boundaries and are
    never collapsed. Standalone French punctuation tokens are attached to the
    preceding word atom so punctuation cannot become an orphan line.
    """
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    if not text.strip():
        return "", [], [], []

    space_width = advances[" "]
    lines: list[str] = []
    line_widths: list[int] = []
    line_char_counts: list[int] = []
    line_parser_unit_counts: list[int] = []

    for segment in text.split("\n"):
        atoms = _wrap_atoms(segment)
        if not atoms:
            # Semantic layout hints never intentionally generate blank lines.
            # Ignore an accidental empty segment rather than creating vertical
            # motion that was not present in the localized prose.
            continue

        line_atoms: list[str] = []
        line_width = 0
        line_chars = 0
        line_parser_units = 0

        def flush() -> None:
            nonlocal line_atoms, line_width, line_chars, line_parser_units
            if not line_atoms:
                return
            lines.append(" ".join(line_atoms))
            line_widths.append(line_width)
            line_char_counts.append(line_chars)
            line_parser_unit_counts.append(line_parser_units)
            line_atoms = []
            line_width = 0
            line_chars = 0
            line_parser_units = 0

        for atom in atoms:
            atom_width = _markup_width(atom, advances, placeholder_width)
            atom_chars = _markup_chars(atom, placeholder_chars)
            placeholder_count = len(PLAYER_PLACEHOLDER_RE.findall(atom))
            atom_parser_units = atom_chars + placeholder_count * placeholder_parser_safety_units
            if atom_width > max_pixels:
                raise ValueError(
                    f"Unbreakable dialogue word exceeds {max_pixels}px: {atom!r} ({atom_width}px)"
                )
            if atom_parser_units > max_chars:
                raise ValueError(
                    f"Unbreakable dialogue word exceeds {max_chars} parser units: "
                    f"{atom!r} ({atom_parser_units})"
                )

            candidate_width = atom_width if not line_atoms else line_width + space_width + atom_width
            candidate_chars = atom_chars if not line_atoms else line_chars + 1 + atom_chars
            candidate_units = (
                atom_parser_units if not line_atoms else line_parser_units + 1 + atom_parser_units
            )
            if line_atoms and (candidate_width > max_pixels or candidate_units > max_chars):
                flush()
            if line_atoms:
                line_width += space_width
                line_chars += 1
                line_parser_units += 1
            line_atoms.append(atom)
            line_width += atom_width
            line_chars += atom_chars
            line_parser_units += atom_parser_units

        flush()

    return "\n".join(lines), line_widths, line_char_counts, line_parser_unit_counts


def _page_line_counts(line_count: int, *, page_lines: int = DIALOGUE_PAGE_LINES) -> tuple[int, ...]:
    """Fallback distribution when no safe sentence-boundary page split exists.

    The stock box safely exposes three physical text lines. The preferred
    extra-page path breaks between complete sentences. Only when that cannot be
    done safely do we balance four lines as 2+2, five as 3+2 and six as 3+3 to
    avoid a one-line orphan page.
    """
    if line_count <= page_lines:
        return (line_count,)
    if line_count > page_lines * 2:
        raise ValueError(
            f"Extra-page pilot supports at most {page_lines * 2} wrapped lines; got {line_count}"
        )
    first = page_lines
    second = line_count - first
    if second == 1:
        first -= 1
        second += 1
    return (first, second)


def _balanced_wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    line_count: int,
    page_line_counts: tuple[int, ...],
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Reflow plain prose into an exact number of balanced lines/pages.

    Semantic hard-line hints are intentionally not moved by this optimizer. If
    ``text`` contains such a hint, callers must use :func:`wrap_markup` for the
    relevant page piece instead.
    """
    if "\n" in text:
        raise ValueError("Balanced wrapper cannot move semantic hard-line hints")
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    atoms = _wrap_atoms(text)
    if not atoms:
        return "", [], [], []
    if line_count < 1 or line_count > len(atoms):
        raise ValueError(f"Cannot wrap {len(atoms)} atom(s) into exactly {line_count} line(s)")
    if sum(page_line_counts) != line_count:
        raise ValueError("Page-line distribution does not equal requested line count")

    page_break_after: set[int] = set()
    running = 0
    for count in page_line_counts[:-1]:
        running += count
        page_break_after.add(running)

    weak_end_words = {
        "à", "au", "aux", "de", "du", "des", "et", "ou", "un", "une",
        "le", "la", "les", "ce", "ces", "tout", "toute", "tous", "toutes",
        "en", "dans", "sur", "pour", "avec", "sans", "que", "qui", "ne",
        "se", "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes",
        "notre", "votre",
    }

    def weak_key(atom: str) -> str:
        # Standalone punctuation may be attached inside an atom (``loin !``).
        # The first lexical token is therefore the relevant weak-word test.
        return atom.split()[0].strip(".,!?;:…“”\"'()[]").lower()

    def ends_sentence(atom: str) -> bool:
        return bool(re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", atom))

    total_width = _markup_width(text, advances, placeholder_width)
    target_width = min(max_pixels, total_width / line_count)

    metrics_cache: dict[tuple[int, int], tuple[str, int, int, int]] = {}

    def metrics(start: int, end: int) -> tuple[str, int, int, int]:
        key = (start, end)
        cached = metrics_cache.get(key)
        if cached is not None:
            return cached
        value = " ".join(atoms[start:end])
        width = _markup_width(value, advances, placeholder_width)
        chars = _markup_chars(value, placeholder_chars)
        placeholders = len(PLAYER_PLACEHOLDER_RE.findall(value))
        parser_units = chars + placeholders * placeholder_parser_safety_units
        result = (value, width, chars, parser_units)
        metrics_cache[key] = result
        return result

    infinity = float("inf")
    memo: dict[tuple[int, int], tuple[float, tuple[tuple[str, int, int, int], ...]]] = {}

    def solve(atom_index: int, line_index: int):
        key = (atom_index, line_index)
        if key in memo:
            return memo[key]
        if line_index == line_count:
            result = (0.0, ()) if atom_index == len(atoms) else (infinity, ())
            memo[key] = result
            return result

        lines_left_after = line_count - line_index - 1
        max_end = len(atoms) - lines_left_after
        best_cost = infinity
        best_path: tuple[tuple[str, int, int, int], ...] = ()
        for end in range(atom_index + 1, max_end + 1):
            value, width, chars, parser_units = metrics(atom_index, end)
            if width > max_pixels or parser_units > max_chars:
                break

            first_atom = atoms[atom_index]
            last_atom = atoms[end - 1]
            cost = (width - target_width) ** 2
            if _PUNCTUATION_ATOM_RE.fullmatch(first_atom):
                cost += 100_000
            if weak_key(last_atom) in weak_end_words:
                cost += 3_500
            if ends_sentence(last_atom):
                cost -= 700

            one_based_line = line_index + 1
            if one_based_line in page_break_after:
                if weak_key(last_atom) in weak_end_words:
                    cost += 7_000
                if ends_sentence(last_atom):
                    cost -= 1_200

            child_cost, child_path = solve(end, line_index + 1)
            total_cost = cost + child_cost
            if total_cost < best_cost:
                best_cost = total_cost
                best_path = ((value, width, chars, parser_units),) + child_path

        memo[key] = (best_cost, best_path)
        return memo[key]

    cost, path = solve(0, 0)
    if cost == infinity or len(path) != line_count:
        raise ValueError(f"No valid balanced {line_count}-line wrapping exists")

    lines = [entry[0] for entry in path]
    widths = [entry[1] for entry in path]
    char_counts = [entry[2] for entry in path]
    parser_units = [entry[3] for entry in path]

    parts: list[str] = []
    cursor = 0
    for count in page_line_counts:
        parts.append("\n".join(lines[cursor:cursor + count]))
        cursor += count
    return "\f".join(parts), widths, char_counts, parser_units



def _sentence_boundary_positions(text: str) -> tuple[int, ...]:
    """Return conservative page-break positions after complete sentences.

    Android prose is already normalized to single spaces before this helper is
    called. ``!``, ``?`` and the Unicode ellipsis are always strong boundaries.
    A full stop is accepted when it terminates a normal word (rather than a
    one/two-letter abbreviation); for ``...`` only the final dot is considered.
    Closing quote/bracket punctuation remains attached to the sentence.
    """
    positions: list[int] = []
    closers = "\"”»')]"
    for index, char in enumerate(text):
        if char not in ".!?…":
            continue
        # For an ellipsis written as three dots, consider only the final dot.
        if char == "." and index + 1 < len(text) and text[index + 1] == ".":
            continue
        if char == "." and not (index >= 2 and text[index - 1] == "." and text[index - 2] == "."):
            # Avoid treating short abbreviations such as ``M. Dupont`` as a
            # semantic page boundary. This is deliberately conservative.
            start = index - 1
            while start >= 0 and (text[start].isalpha() or text[start] in "'-"):
                start -= 1
            word = text[start + 1:index]
            if 0 < len(word) <= 2:
                continue

        end = index + 1
        while end < len(text) and text[end] in closers:
            end += 1
        if end == len(text):
            continue  # no following page
        if not text[end].isspace():
            continue
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text):
            positions.append(end)
    return tuple(positions)



def _comma_boundary_positions(text: str) -> tuple[int, ...]:
    """Return conservative weak clause boundaries immediately after commas."""
    positions: list[int] = []
    for index, char in enumerate(text):
        if char != ",":
            continue
        end = index + 1
        if end >= len(text) or not text[end].isspace():
            continue
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text):
            positions.append(end)
    return tuple(positions)


def _semantic_wrap_plain_segment(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Wrap one segment while preferring natural French clause boundaries.

    Strong sentence boundaries are preserved whenever each sentence can be
    laid out independently without exceeding one three-line SNES page. This is
    intentionally allowed to use an otherwise-unused third line: readability
    takes precedence over packing unrelated sentences together. For a single
    sentence that needs exactly two lines, a comma may be used as a weaker
    boundary when it yields a substantially better-balanced pair of lines.
    """
    baseline = wrap_markup(text, advances, max_pixels=max_pixels, max_chars=max_chars)
    if not text.strip() or "\n" in text:
        return baseline

    def wrap_one_sentence(sentence: str):
        result = wrap_markup(sentence, advances, max_pixels=max_pixels, max_chars=max_chars)
        if len(result[1]) != 2:
            return result
        baseline_balance = abs(result[1][0] - result[1][1])
        best = None
        comma_boundaries = _comma_boundary_positions(sentence)
        # Multiple commas often encode discourse rhythm or parenthetical
        # phrasing (``Pendant ce temps, toi, file...``). Do not guess which
        # comma is semantic in that case; keep weak comma optimization limited
        # to a single unambiguous clause boundary.
        if len(comma_boundaries) != 1:
            return result
        for boundary in comma_boundaries:
            first = sentence[:boundary].strip()
            second = sentence[boundary:].strip()
            if not first or not second:
                continue
            first_result = wrap_markup(first, advances, max_pixels=max_pixels, max_chars=max_chars)
            second_result = wrap_markup(second, advances, max_pixels=max_pixels, max_chars=max_chars)
            if len(first_result[1]) != 1 or len(second_result[1]) != 1:
                continue
            # Avoid turning a tiny tail/head into a decorative line. The comma
            # boundary is only a soft preference when both clauses have enough
            # visual substance and materially improve balance.
            w1, w2 = first_result[1][0], second_result[1][0]
            if min(w1, w2) < 72:
                continue
            balance = abs(w1 - w2)
            improvement = baseline_balance - balance
            if improvement < 24:
                continue
            candidate = (
                first_result[0] + "\n" + second_result[0],
                first_result[1] + second_result[1],
                first_result[2] + second_result[2],
                first_result[3] + second_result[3],
            )
            if best is None or balance < best[0]:
                best = (balance, candidate)
        return best[1] if best is not None else result

    boundaries = _sentence_boundary_positions(text)
    if boundaries:
        starts = (0,) + boundaries
        ends = boundaries + (len(text),)
        sentence_results = []
        for start, end in zip(starts, ends, strict=True):
            sentence = text[start:end].strip()
            if not sentence:
                continue
            sentence_results.append(wrap_one_sentence(sentence))
        semantic_line_count = sum(len(result[1]) for result in sentence_results)
        # Never create an extra page just for aesthetics. Within an already
        # available three-line page, however, preserving sentence starts is a
        # deliberate readability preference.
        if sentence_results and semantic_line_count <= DIALOGUE_PAGE_LINES:
            lines: list[str] = []
            widths: list[int] = []
            chars: list[int] = []
            units: list[int] = []
            for wrapped, part_widths, part_chars, part_units in sentence_results:
                lines.extend(wrapped.split("\n"))
                widths.extend(part_widths)
                chars.extend(part_chars)
                units.extend(part_units)
            return "\n".join(lines), widths, chars, units

    return wrap_one_sentence(text)


def semantic_wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Wrap localized prose with semantic sentence/clause line preferences.

    Explicit hard-line hints (speaker changes and attributions) remain
    mandatory. Each side of such a hint is optimized independently, then the
    original hard boundary is restored.
    """
    if "\n" not in text:
        return _semantic_wrap_plain_segment(
            text, advances, max_pixels=max_pixels, max_chars=max_chars
        )

    all_lines: list[str] = []
    widths: list[int] = []
    chars: list[int] = []
    units: list[int] = []
    for segment in text.split("\n"):
        if not segment.strip():
            continue
        wrapped, part_widths, part_chars, part_units = _semantic_wrap_plain_segment(
            segment, advances, max_pixels=max_pixels, max_chars=max_chars
        )
        all_lines.extend(wrapped.split("\n"))
        widths.extend(part_widths)
        chars.extend(part_chars)
        units.extend(part_units)
    return "\n".join(all_lines), widths, chars, units

def _sentence_aware_extra_page_wrap(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    prefer_semantic_line_breaks: bool = True,
) -> tuple[str, list[int], list[int], list[int], tuple[int, int], str]:
    """Wrap one overflowing prose block onto at most two pages.

    Semantic hard-line hints (speaker changes / dash attributions) are the
    strongest page-boundary candidates: if the text cannot stay on one page and
    one of those boundaries leaves both sides within three lines, page there.
    Otherwise prefer the latest complete-sentence boundary. The old balanced
    fallback remains only for prose without a usable semantic boundary.
    """

    def wrap_piece(piece: str) -> tuple[str, list[int], list[int], list[int]]:
        wrapper = semantic_wrap_markup if prefer_semantic_line_breaks else wrap_markup
        return wrapper(piece, advances, max_pixels=max_pixels, max_chars=max_chars)

    # First honor explicit semantic line boundaries inserted by the formatter.
    hard_candidates: list[tuple[int, str, str, tuple, tuple]] = []
    for index, char in enumerate(text):
        if char != "\n":
            continue
        first = text[:index].strip()
        second = text[index + 1:].strip()
        if not first or not second:
            continue
        try:
            first_result = wrap_piece(first)
            second_result = wrap_piece(second)
        except ValueError:
            continue
        if not (1 <= len(first_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        if not (1 <= len(second_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        hard_candidates.append((index, first, second, first_result, second_result))

    if hard_candidates:
        # Keep as much complete dialogue as possible on page 1 while ensuring
        # the new speaker/attribution begins at the top of page 2.
        _, first, second, first_result, second_result = max(hard_candidates, key=lambda item: item[0])
        first_wrapped, first_widths, first_chars, first_units = first_result
        second_wrapped, second_widths, second_chars, second_units = second_result
        return (
            first_wrapped + "\f" + second_wrapped,
            first_widths + second_widths,
            first_chars + second_chars,
            first_units + second_units,
            (len(first_widths), len(second_widths)),
            "semantic_hard_boundary",
        )

    candidates: list[tuple[int, str, str, tuple, tuple]] = []
    for boundary in _sentence_boundary_positions(text):
        first = text[:boundary].strip()
        second = text[boundary:].strip()
        if not first or not second:
            continue
        try:
            first_result = wrap_piece(first)
            second_result = wrap_piece(second)
        except ValueError:
            continue
        if not (1 <= len(first_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        if not (1 <= len(second_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        candidates.append((boundary, first, second, first_result, second_result))

    if candidates:
        boundary, first, second, first_result, second_result = max(candidates, key=lambda item: item[0])

        def balanced_or_greedy(piece: str, result: tuple[str, list[int], list[int], list[int]]):
            wrapped, widths, chars, units = result
            if "\n" in piece:
                return wrapped, widths, chars, units
            return _balanced_wrap_markup(
                piece,
                advances,
                line_count=len(widths),
                page_line_counts=(len(widths),),
                max_pixels=max_pixels,
                max_chars=max_chars,
            )

        first_wrapped, first_widths, first_chars, first_units = balanced_or_greedy(first, first_result)
        second_wrapped, second_widths, second_chars, second_units = balanced_or_greedy(second, second_result)
        return (
            first_wrapped + "\f" + second_wrapped,
            first_widths + second_widths,
            first_chars + second_chars,
            first_units + second_units,
            (len(first_widths), len(second_widths)),
            "sentence_boundary",
        )

    greedy, widths, chars, units = wrap_piece(text)
    page_line_counts = _page_line_counts(len(widths))
    if len(page_line_counts) != 2:
        raise ValueError("Extra-page formatter inserts exactly one additional page")

    # If semantic hard-line hints exist but none can be used as a safe page
    # boundary, never rebalance across them. Preserve the hinted lines and only
    # divide the already-wrapped output into the deterministic 2-page fallback.
    if "\n" in text:
        greedy_lines = greedy.split("\n")
        first_count, second_count = page_line_counts
        first = "\n".join(greedy_lines[:first_count])
        second = "\n".join(greedy_lines[first_count:first_count + second_count])
        return greedy and (
            first + "\f" + second,
            widths,
            chars,
            units,
            page_line_counts,
            "semantic_preserving_fallback",
        )

    wrapped, widths, chars, units = _balanced_wrap_markup(
        text,
        advances,
        line_count=sum(page_line_counts),
        page_line_counts=page_line_counts,
        max_pixels=max_pixels,
        max_chars=max_chars,
    )
    return wrapped, widths, chars, units, page_line_counts, "balanced_fallback"


def event_text_index(document: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return ``(text-id -> token metadata, event-id -> event)``."""
    by_id: dict[str, dict] = {}
    by_event: dict[str, dict] = {}
    for event in document.get("events", []):
        event_id = event["event_id"]
        by_event[event_id] = event
        for token_index, token in enumerate(event.get("tokens", [])):
            if token.get("type") != "text":
                continue
            text_id = token["id"]
            if text_id in by_id:
                raise ValueError(f"Duplicate dialogue source ID {text_id}")
            by_id[text_id] = {
                "event_id": event_id,
                "token_index": token_index,
                "source": token["source"],
            }
    return by_id, by_event


def binding_slots(document: dict, mapping: dict) -> list[BindingSlot]:
    """Recover the exact mapped text/PLAYER_NAME stream from canonical tokens.

    Mappings may begin or end immediately next to a ``PLAYER_NAME`` command.
    The aligner includes that placeholder in ``source_display`` even when the
    position-derived SNES text ID itself lies only on one side of the command.
    Search only those adjacent PLAYER_NAME boundaries and accept a span only
    when its canonical rendering equals the established alignment exactly.

    Any other command, glyph, or unmapped text crossed by a mapping is still
    rejected. This preserves the conservative structural contract.
    """
    by_id, by_event = event_text_index(document)
    snes_ids = mapping.get("snes_ids", [])
    if not snes_ids:
        raise ValueError("Dialogue mapping has no SNES text IDs")
    try:
        event_id = by_id[snes_ids[0]]["event_id"]
    except KeyError as exc:
        raise ValueError(f"Unknown dialogue source ID {snes_ids[0]}") from exc
    if any(by_id[text_id]["event_id"] != event_id for text_id in snes_ids):
        raise ValueError("One dialogue mapping spans multiple SNES events")
    if mapping.get("event_id") != event_id:
        raise ValueError(
            f"Dialogue mapping event mismatch for {snes_ids[0]}: {mapping.get('event_id')} vs {event_id}"
        )

    event = by_event[event_id]
    tokens = event["tokens"]
    token_indexes = [by_id[text_id]["token_index"] for text_id in snes_ids]
    if token_indexes != sorted(token_indexes):
        raise ValueError(f"Dialogue mapping SNES IDs are not in token order: {snes_ids}")
    selected = set(snes_ids)

    def is_player(index: int) -> bool:
        if not (0 <= index < len(tokens)):
            return False
        token = tokens[index]
        return token.get("type") == "command" and token.get("name") == "PLAYER_NAME"

    starts = [token_indexes[0]]
    cursor = token_indexes[0] - 1
    while is_player(cursor):
        starts.append(cursor)
        cursor -= 1
    ends = [token_indexes[-1]]
    cursor = token_indexes[-1] + 1
    while is_player(cursor):
        ends.append(cursor)
        cursor += 1

    def slots_for_span(span_start: int, span_end: int) -> list[BindingSlot] | None:
        slots: list[BindingSlot] = []
        for token in tokens[span_start:span_end + 1]:
            kind = token.get("type")
            if kind == "text":
                if token["id"] not in selected:
                    return None
                slots.append(TextSlot(token["id"], token["source"]))
            elif kind == "command" and token.get("name") == "PLAYER_NAME":
                args = token.get("args", "00").split()
                if not args:
                    raise ValueError("PLAYER_NAME command has no index")
                slots.append(PlayerSlot(int(args[0], 16)))
            else:
                return None
        return slots

    expected = mapping.get("source_display", "")
    matches: list[tuple[int, int, list[BindingSlot]]] = []
    for span_start in starts:
        for span_end in ends:
            if span_start > token_indexes[0] or span_end < token_indexes[-1]:
                continue
            slots = slots_for_span(span_start, span_end)
            if slots is None:
                continue
            rendered = "".join(
                slot.source if isinstance(slot, TextSlot) else f"%S({slot.index},0)"
                for slot in slots
            )
            if rendered == expected:
                matches.append((span_start, span_end, slots))

    if not matches:
        # Preserve the old diagnostic when the canonical structure no longer
        # reproduces the established alignment.
        base_slots = slots_for_span(token_indexes[0], token_indexes[-1])
        if base_slots is None:
            for token in tokens[token_indexes[0]:token_indexes[-1] + 1]:
                kind = token.get("type")
                if kind == "text" and token.get("id") not in selected:
                    raise ValueError(
                        f"Mapping {snes_ids} crosses unmapped text token {token['id']}; defer structural binding"
                    )
                if kind != "text" and not (kind == "command" and token.get("name") == "PLAYER_NAME"):
                    raise ValueError(
                        f"Mapping {snes_ids} crosses {kind} {token.get('name', '')!r}; defer structural binding"
                    )
        raise ValueError(
            f"Canonical binding stream for {snes_ids} no longer equals alignment source_display"
        )

    # Prefer the narrowest exact canonical span. More than one equally narrow
    # exact span would be structurally ambiguous and is therefore rejected.
    width = min(end - start for start, end, _ in matches)
    narrow = [entry for entry in matches if entry[1] - entry[0] == width]
    if len(narrow) != 1:
        raise ValueError(f"Ambiguous adjacent PLAYER_NAME binding for {snes_ids}")
    return narrow[0][2]


def _leading_newlines(text: str) -> int:
    return len(text) - len(text.lstrip("\n"))


def _trailing_newlines(text: str) -> int:
    return len(text) - len(text.rstrip("\n"))


def _leading_newline_follows_wait(document: dict, text_id: str) -> bool:
    """Return whether a text token starts immediately after an existing WAIT.

    Stock scripts often combine ``WAIT`` with a leading newline in the next
    text chunk to scroll the previous three-line window away. For localized
    chunks we can keep the existing WAIT, emit one TEXT_CLEAR, and drop that
    synthetic blank line instead.
    """
    by_id, by_event = event_text_index(document)
    meta = by_id[text_id]
    tokens = by_event[meta["event_id"]]["tokens"]
    index = meta["token_index"]
    if index <= 0:
        return False
    previous = tokens[index - 1]
    return previous.get("type") == "command" and previous.get("name") == "WAIT"


def source_visible_line_budget(source_display: str) -> int:
    """Return the explicit source-line budget used by the first format pilot.

    This deliberately handles only source spans that already carry explicit
    line structure. Later expansion can add a validated stock auto-wrap simulator
    for long no-newline source spans.
    """
    lines = [line for line in source_display.split("\n") if line.strip()]
    return max(1, len(lines))


def bind_wrapped_markup(slots: list[BindingSlot], wrapped: str) -> dict[str, str]:
    """Replace placeholders with existing PLAYER_NAME slots and return text values.

    Each literal run between placeholders must map to exactly one existing text
    token. Multi-text runs are intentionally deferred until a later validated
    structural-distribution step.
    """
    placeholders = list(PLAYER_PLACEHOLDER_RE.finditer(wrapped))
    literal_runs: list[str] = []
    cursor = 0
    for match in placeholders:
        literal_runs.append(wrapped[cursor:match.start()])
        cursor = match.end()
    literal_runs.append(wrapped[cursor:])

    slot_runs: list[list[TextSlot]] = [[]]
    player_indexes: list[int] = []
    for slot in slots:
        if isinstance(slot, TextSlot):
            slot_runs[-1].append(slot)
        else:
            player_indexes.append(slot.index)
            slot_runs.append([])

    markup_indexes = [int(match.group(1)) for match in placeholders]
    if tuple(markup_indexes) != tuple(player_indexes):
        raise ValueError(
            f"French PLAYER_NAME sequence {tuple(markup_indexes)} does not match SNES {tuple(player_indexes)}"
        )
    if len(literal_runs) != len(slot_runs):
        raise AssertionError("Placeholder/literal run accounting mismatch")

    translations: dict[str, str] = {}
    for run, text_slots in zip(literal_runs, slot_runs, strict=True):
        if not text_slots:
            if run:
                raise ValueError(
                    "Localized literal text exists where the SNES stream has no text token around PLAYER_NAME"
                )
            continue
        # Adjacent text tokens have no intervening event side effect: their
        # serialized bytes are one continuous source stream. Put the localized
        # literal run in the first token and explicitly empty the remaining
        # contiguous tokens. This is byte-equivalent to concatenating them and
        # avoids inventing an arbitrary sentence-to-token split.
        translations[text_slots[0].text_id] = run
        for slot in text_slots[1:]:
            translations[slot.text_id] = ""
    return translations


def format_mapping(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    allow_one_extra_page: bool = False,
    use_physical_page_capacity: bool = False,
    prefer_semantic_line_breaks: bool = True,
) -> tuple[dict[str, str], dict]:
    """Format one already accepted mapping into existing SNES text-token values."""
    slots = binding_slots(document, mapping)
    source_display = mapping["source_display"]
    french_raw = mapping.get("french_display", "")
    if not french_raw:
        raise ValueError("Accepted dialogue mapping has no French Android text")

    source_placeholders = tuple(slot.index for slot in slots if isinstance(slot, PlayerSlot))
    french_normalized = normalize_android_french(french_raw)
    french_layout, layout_hints = apply_semantic_layout_hints(french_normalized)
    french_placeholders = placeholder_sequence(french_layout)
    if source_placeholders != french_placeholders:
        raise ValueError(
            f"French PLAYER_NAME sequence {french_placeholders} does not match SNES {source_placeholders}"
        )

    # Preserve only hard leading/trailing line motion from the canonical SNES
    # token stream. Android presentation wraps are discarded and recreated from
    # validated VWF widths.
    text_slots = [slot for slot in slots if isinstance(slot, TextSlot)]
    lead = _leading_newlines(text_slots[0].source)
    trail = _trailing_newlines(text_slots[-1].source)
    inserted_leading_clear = bool(lead and _leading_newline_follows_wait(document, text_slots[0].text_id))
    if inserted_leading_clear:
        lead = 0

    wrapper = semantic_wrap_markup if prefer_semantic_line_breaks else wrap_markup
    wrapped, widths, char_counts, parser_unit_counts = wrapper(
        french_layout, advances, max_pixels=max_pixels
    )
    source_line_budget = source_visible_line_budget(source_display)
    line_budget = DIALOGUE_PAGE_LINES if use_physical_page_capacity else source_line_budget
    inserted_page_breaks = 0
    page_line_counts = (len(widths),)
    page_break_strategy: str | None = None
    if len(widths) > line_budget:
        if not allow_one_extra_page:
            raise ValueError(
                f"French VWF needs {len(widths)} line(s), available page budget is {line_budget}: {mapping['snes_ids']}"
            )
        if not use_physical_page_capacity and line_budget != DIALOGUE_PAGE_LINES:
            raise ValueError(
                f"Extra-page pilot requires a {DIALOGUE_PAGE_LINES}-line source page; "
                f"source span exposes {line_budget}: {mapping['snes_ids']}"
            )
        (
            wrapped,
            widths,
            char_counts,
            parser_unit_counts,
            page_line_counts,
            page_break_strategy,
        ) = _sentence_aware_extra_page_wrap(
            french_layout,
            advances,
            max_pixels=max_pixels,
            max_chars=DIALOGUE_WRAP_CHARS,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        )
        inserted_page_breaks = 1

    translations = bind_wrapped_markup(slots, wrapped)
    first_id = text_slots[0].text_id
    last_id = text_slots[-1].text_id
    translations[first_id] = "\n" * lead + translations[first_id]
    if inserted_leading_clear:
        translations[first_id] = TRANSLATION_CLEAR + translations[first_id]
    translations[last_id] = translations[last_id] + "\n" * trail

    # Final byte-level charset check before the translation JSON reaches 08.
    for text_id, text in translations.items():
        for char in text:
            if char in ("\n", "\f", TRANSLATION_CLEAR):
                continue
            if char not in TEXT_TO_CODE:
                raise ValueError(f"{text_id}: unsupported formatted character {char!r}")

    report = {
        "event_id": mapping["event_id"],
        "snes_ids": mapping["snes_ids"],
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": source_display,
        "android_french_raw": french_raw,
        "android_french_normalized": french_normalized,
        "layout_markup_before_wrap": french_layout,
        "layout_hints": layout_hints,
        "formatted_markup": "\n" * lead + wrapped + "\n" * trail,
        "line_widths_pixels": widths,
        "line_decoded_character_counts": char_counts,
        "line_parser_unit_counts": parser_unit_counts,
        "source_visible_line_budget": source_line_budget,
        "effective_line_budget": line_budget,
        "physical_page_capacity_mode": use_physical_page_capacity,
        "semantic_line_break_preferences": prefer_semantic_line_breaks,
        "page_line_counts": list(page_line_counts),
        "inserted_page_break_count": inserted_page_breaks,
        "inserted_leading_clear": inserted_leading_clear,
        "page_break_encoding": "WAIT $00 + TEXT_CLEAR" if inserted_page_breaks else None,
        "page_break_strategy": page_break_strategy,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in mapping["snes_ids"]
        ],
    }
    return translations, report


def make_translation_document(entries: Iterable[tuple[str, str]], *, group: str) -> dict:
    ordered = [{"id": text_id, "text": text} for text_id, text in entries]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "dialogues.json",
        "groups": [{"group": group, "entries": ordered}],
    }
