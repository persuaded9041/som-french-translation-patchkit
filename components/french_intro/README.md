# French intro

Owns the validated French text/data payload for new-game event `$0400`. It does
**not** own the VWF renderer; that runtime belongs to `vwf_intro`.

## Inputs and responsibilities

Canonical prose comes from the root assets only:

- `assets/intro_event.json` — clean-USA source extraction for the eight text
  parts of event `$0400`;
- `translations/intro_event_french.json` — validated French translations;
- `assets/text/intro_layout.json` — component-local structural metadata: word
  counts per line/page, never a parallel prose source.

The builder validates the root source against a fresh parse of the clean ROM,
then:

- rebuilds event `$0400` with the validated line/page layout and WAIT/CLEAR
  timing;
- installs the `full_french` direct-glyph profile (`$D4-$E5`) in the stock font;
- raises the standalone direct/DTE threshold from `$D3` to `$E6`;
- generates the 25-pair intro-private DTE table and its context-gated loader;
- relocates unchanged stock events `$0401-$040F` to `$CA:FF70-$FFB7` and
  updates their 15 stock event pointers, leaving room for the enlarged `$0400`.

The generated French payload has the runtime-validated exclusive end `$0E8B`.
The builder deliberately rejects any layout/text change that moves that endpoint:
`vwf_intro` owns a VWF gate calibrated to exactly `$CA:0C02-$0E8A` and must be
revalidated before the contract can change.

## Ownership boundary with `vwf_intro`

`french_intro` owns translation, glyph/DTE data and the event rebuild.
`vwf_intro` owns the VWF renderer, shared private parser buffer, width/framing
helpers, compositor, outline behavior and WAIT-resume cursor handling.

Both components independently relocate `$0401-$040F`; those data/pointer writes
are intentionally byte-identical when combined. For the intended in-game
presentation, use both components; `all.ips` includes both.

## Build

```bash
python3 components/french_intro/build_patch.py "Secret of Mana (USA).sfc"
```

See `docs/MEMORY_MAP.md` for the complete functional write map.
