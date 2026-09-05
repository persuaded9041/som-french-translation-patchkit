# Startup/opening text extraction

`assets/opening_text.json` extracts user-visible stock strings from the
compressed title/opening arrangement at ROM `$07B480`. This renderer uses a
different fixed-width encoding from normal event/DTE text, so it has its own
extractor.

The source asset contains **24 records**:

- 13 scrolling prologue lines;
- the copyright line, `all rights reserved.` and `licensed by nintendo`;
- `multi player adapter error`;
- the four stock startup credits;
- the three Super Famicom / Super NES compatibility-warning lines.

The copyright record mixes ordinary characters with dedicated title-font tiles.
The extractor validates the stock tile pattern and exposes its logical source as
`© 1993 SQUARE CO., LTD.`. Graphic-only title/logo data and layout/indent bytes
are deliberately not duplicated as text.

Component `04_french_opening` remains the canonical writer for this compressed arrangement and now consumes `translations/opening_text_french.json`. Because individual strings only acquire stable positions after decompression, IDs use `C7:B480+<decompressed offset>`. The French-only translation credit uses the explicit `new:` namespace because it has no clean-ROM source position.
