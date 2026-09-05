# Text reverse-engineering research notes

This file preserves the research trail behind the root text inventory so the
search can be resumed later without repeating the same exploratory work.

## Goal and method

The goal was to find **user-visible static strings**, not merely byte sequences
that happen to decode as English through Secret of Mana's dense text/DTE codec.
A candidate family was promoted to a canonical asset only after establishing a
real access mechanism: event pointer, resource table, menu descriptor, direct
code reference, or a known decompressor/renderer path.

The investigation therefore proceeded in two stages:

1. trace known text engines/tables and establish exact boundaries;
2. scan remaining ROM regions for plausible strings/pointers and then work
   backwards from every promising match to code or data references.

## Proven families

### Event scripts: `$C9/$CA`

The stock event system has 2048 scripts (`$0000-$07FF`). `$C9:0000` contains the
first 1024 16-bit pointers and `$CA:0000` contains the second 1024. Event `$07FF`
can use the next CA table entry as its upper bound because the table continues
with non-event text pointers. `$03FF` has no C9 sentinel and is explicitly
validated as the stock three-byte terminal script `14 FD 00`.

All 2048 scripts parse with the structural event codec. 714 contain text; event
`$0400` is owned by component 05 and is extracted separately, leaving 713 in
`dialogues.json`.

### Post-event `$CA` resources

The same CA table continues at table index `$0400` with 513 null-terminated
resources (`$000-$200`). The first string is `$CA:98E1`; in the clean ROM every
next pointer immediately follows the previous terminator. This gives a strong
full-table/full-blob round-trip invariant.

These are names, descriptions, locations, menu labels and two system messages,
not missing NPC/story event scripts.

### Interface/help table: `$C0:33B5`

A 24-bit pointer table begins at `$C0:33B5`. An early hypothesis treated the
first five C0 pointers as the whole family. Deeper inspection corrected this:
the table contains **nine** valid text pointers, five into C0 followed by four
into C7. The next three bytes are ordinary non-pointer data and provide the
structural end.

The nine blocks contain 27 visible help/status rows. Blank separators and layout
margins are structural bytes rather than translation entries.

### Native menu/status text: `$C7`

Nine packed menu resources occupy `$C7:7313-$74E9` and are referenced by the
11-record menu descriptor table near `$C7:780A`. Nearby fixed/status strings,
weapon names and templates form additional C7 records. The inventory now stores
logical translatable fragments instead of whole padding-heavy menu blobs; layout
bytes and dynamic placeholders remain derived from the ROM.

The two GAME FILE level-prefix characters at ROM `0x0753C9` / `$C7:53C9` and
`0x075AF1` / `$C7:5AF1` are direct code/data writes rather than normal strings.
They were added because component 03 proves they are user-visible text sources.

### Battle message pool: `$C0:5E6B-$6380`

The battle pool contains 109 physical null-terminated records. An 88-entry
16-bit pointer table at `$C0:5DBB` references most of them; 21 additional records
are referenced directly by battle code. Following only the table would therefore
have missed real strings.

### Shop/forge mini-events: `$D9:FE20-$FEF3`

This family was discovered during the aggressive follow-up scan. Readable strings
such as `Thank you!`, `Sorry, that's not enough.` and `Okay! Let's forge it!`
appeared around `$D9:FE22` but were absent from every earlier asset.

Nine hard-coded `LDX #$xxxx` operands in bank C0 point to nine contiguous D9
mini-event scripts. Two dispatch paths set live event bank `$1D03` to `$D9`, copy
X into the live event pointer and invoke the stock event engine. Each script is
`$7F $52 <text> $00`. This code trace is why the strings are considered proven
rather than search false positives.

### Compressed startup/title arrangement

Component 04 already established the decompressor and renderer for the block
beginning at ROM `0x07B480` / `$C7:B480`. The canonical source inventory extracts
24 user-visible strings from the decompressed arrangement: 13 prologue lines,
legal/copyright strings, multiplayer error, four stock credits and three
compatibility-warning lines.

Because these strings do not have individual physical addresses inside the
compressed byte stream, their stable IDs use `$C7:B480+<decompressed offset>`.

## Aggressive follow-up audit

After the first inventory, the following searches were used specifically to look
for missed families:

- all direct calls to the stock event executor at `$C0:0092`;
- all direct writes to the live event-bank byte `$1D03`;
- plausible runs of 24-bit HiROM text pointers;
- plausible same-bank 16-bit pointer tables;
- null-terminated strings decodable through the stock text/DTE codec;
- ordinary ASCII runs;
- readable runs adjacent to already established text engines.

The fixed-source event-executor paths reduce to the already known C0 battle path,
the newly discovered D9 shop/forge path, and dynamic WRAM-built scripts. Direct
`$1D03` stores similarly resolve to known fixed banks (`$C0`, `$C9/$CA`, `$D9`)
or dynamic WRAM (`$7E`).

No second coherent, code-referenced static family was found after the D9 pool.
Most remaining English-looking hits occur in executable code, graphics,
compressed/opaque data, or arise accidentally because DTE bytes map densely to
letters.

## What is *not* claimed

The inventory is strong evidence for broad coverage of **static user-visible
string data** in the clean USA ROM; it is not a mathematical proof that every
visible letter in the game is represented here.

Potential future research areas include:

- strings assembled dynamically in WRAM;
- graphical lettering/logos rather than text-engine strings;
- single-character literals embedded in code that are not yet tied to a known UI
  behavior;
- unused/unreachable text paths;
- data decoded by a renderer or decompressor not yet identified.

When resuming the search, require an actual renderer/reference trace before
adding a new canonical family. Do not promote a candidate solely because it
looks like English after decoding.

## Checkpoint for resuming the audit

At this checkpoint the repository has eight canonical static-text families:

```text
assets/dialogues.json
assets/intro_event.json
assets/text_resources.json
assets/interface_text.json
assets/menu_text.json
assets/battle_text.json
assets/shop_text.json
assets/opening_text.json
```

The current extraction exposes 2,918 globally unique translatable source
elements. Every element is identified by source position rather than by a
translator-assigned row number:

- direct ROM strings: canonical HiROM address, e.g. `D9:FE22`;
- compressed opening strings: compressed container address plus deterministic
  decompressed offset, e.g. `C7:B480+09F9`.

`tools/check_text_roundtrip.py` checks global ID uniqueness. Translation files do
not participate in source discovery and live separately under `translations/`.

If the inventory search is resumed, start with the existing deep-audit result
rather than another blind string scan. Useful next questions are specifically:

1. Are there other routines that build display strings dynamically in WRAM and
   copy literal ROM fragments not reached by the known event/menu/battle paths?
2. Are there renderer-specific pointer tables in banks not exercised by the
   known menu descriptors or event executor?
3. Are any single-character literals or very short strings user-visible but too
   short to have appeared in the plausibility scans?
4. Do unused/debug paths reference genuine static text that should be inventoried
   even if normal gameplay cannot reach it?
5. Are there additional compressed containers with a proven text renderer?

For any candidate, trace the runtime access path before adding it to a canonical
asset. Record the pointer/reference mechanism, exact physical boundaries and
round-trip invariant. This avoids reintroducing the false-positive problem caused
by the game's dense DTE encoding.
