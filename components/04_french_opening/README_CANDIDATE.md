# Five startup credits - runtime candidate

This candidate is based on the validated French opening module.

Changes:
- adds `Traduction : E.CHAUVIRE` as a fifth startup credit;
- preserves every existing arrangement offset; the five-credit list is appended at the end of the arrangement;
- redirects the stock credit renderer from relative X `$01BE` to the appended list;
- changes the **actual credit dwell** in the `$8DD0` credit routine from 240 to 180 frames;
- fade-in/fade-out code is unchanged.

Timing rationale:
- stock: `4 * (31 + 240 + 31) = 1208` frames;
- candidate: `5 * (31 + 180 + 31) = 1210` frames.

No previous experimental `300-frame` timer changes are present.
