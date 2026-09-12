# French opening build compression optimization

The `french_opening` component used to be much slower to rebuild than the other
components. On the maintenance benchmark used for this pass, the standalone
component took about 14.7 seconds while most components took roughly 1.4–4.3
seconds.

The bottleneck was the component-local optimal LZ compressor in
`components/french_opening/build_patch.py`, not image loading, source parsing,
IPS generation, or decompression. Approximate isolated compression costs on the
stock blocks were:

- title code (22,227 bytes): ~4.2 s;
- arrangement (7,142 bytes): ~8.8 s;
- font (1,024 bytes): ~0.04 s.

Two output-preserving changes were made:

1. Small-window blocks (the arrangement/font) carry longest-common-prefix
   lengths forward by distance instead of repeatedly comparing the same suffix
   bytes. Match lengths are still scored for the nearest candidate first, so the
   legacy strict tie-breaking is preserved.
2. Large-window blocks (the title code) follow a chain of previous occurrences
   of the same first byte instead of scanning every position in the 4 KiB
   window only to reject almost all of them immediately.

The compression format, dynamic-programming cost function, candidate ordering,
and tie-breaking remain unchanged. The rebuilt `french_opening.ips` is
byte-identical to the pre-optimization patch.

Measured standalone build time fell from ~14.7 s to ~3.3 s in this environment.

## Superseded arrangement path (Round 85.13)

The optimal-compressor improvements above remain active for the title-code and
font blocks. The arrangement itself no longer uses optimal LZ compression as of
Round 85.13: it is emitted as a literal-only stock-format stream at `$EE:A000`
and still loaded by `$C1:0014`. See `OPENING_LITERAL_STREAM_ROUND85_13.md`.
