# French intro

Owns the validated French text payload for new-game event `$0400` without
owning the VWF renderer.

## Responsibilities

- bind the eight validated entries from root `translations/intro_event_french.json`
  to the canonical clean-USA `assets/intro_event.json` source;
- apply `assets/text/intro_layout.json` line/page metadata;
- rebuild event `$0400` with the validated WAIT/CLEAR timing;
- install the French direct glyphs and intro-private DTE table/loader;
- relocate unchanged stock events `$0401-$040F` to `$CA:FF70-$FFB7` so the
  enlarged French `$0400` payload can occupy `$CA:0C02-$0E8A` safely.

The VWF renderer, shared private parser buffer, width table, framing,
compositor, and outline behavior belong to `vwf_intro`.

The current validated French payload ends at exclusive pointer `$0E8B`.
Changing that endpoint is intentionally rejected by this builder because the
runtime window in `vwf_intro` would need explicit revalidation.

For the intended in-game presentation, use this component together with
`vwf_intro`; `all.ips` includes both.
