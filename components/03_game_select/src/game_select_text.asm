; Secret of Mana (USA) - GAME SELECT translation support - validated step 3
; All ROM offsets refer to the clean, unheadered US ROM.
; build_patch.py is the canonical implementation; this file documents the
; relevant structures and patches in assembler form.

; ---------------------------------------------------------------------------
; 1. GAME SELECT label resource
; ---------------------------------------------------------------------------
;
; The stock labels are stored in one 45-byte menu resource in bank C7.
; Runtime testing showed that the physical resource must remain exactly 45
; bytes: changing its size desynchronizes the help-text rendering below the
; menu. The builder therefore relocates the resource but preserves its native
; 45-byte structure.
;
; Stock resource:
;   ROM 077313 / C7:7313
;
; Relocated resource:
;   ROM 074400 / C7:4400
;
; The menu descriptor contains a 16-bit pointer because the resource stays in
; bank C7. The builder changes that pointer at ROM 07780A to $4400.
;
; Logical layout of the 45-byte resource:
;   1 byte   : leading blank
;   8 cells  : SELECT segment (used twice around the D-pad)
;   14 cells : GAME_SELECT / "Votre choix"
;   10 cells : NEW_GAME / "Nouveau"
;   12 cells : GAME_FILE / "Continuer"
;
; The final $00 terminator doubles as the last logical GAME_FILE cell, matching
; the stock resource layout.

org $C7780A
dw $4400

; ---------------------------------------------------------------------------
; 2. Framed-field widths
; ---------------------------------------------------------------------------
;
; Three type-1 menu records store the horizontal size of the framed labels.
; One width unit corresponds to two text cells. The builder derives these
; values from the CSV while preserving a total of 36 framed cells.
;
; Current validated values:
;   GAME_SELECT : $07 = 14 cells
;   NEW_GAME    : $05 = 10 cells
;   GAME_FILE   : $06 = 12 cells

org $C7756D
db $07
org $C77572
db $05
org $C77577
db $06

; ---------------------------------------------------------------------------
; 3. Accented characters
; ---------------------------------------------------------------------------
;
; Step 2 repurposes direct character slots $D4-$E0 for:
;   $D4 Ç  $D5 à  $D6 â  $D7 ç  $D8 é  $D9 è  $DA ê
;   $DB ë  $DC î  $DD ï  $DE ô  $DF ù  $E0 û
;
; Their editable 8x12 glyphs come from ../../../shared/french_charset/french_glyphs.png.
; Character/code assignments come from ../../../shared/french_charset/charset.json. The atlas is an exact
; pixel-for-pixel extraction of the same 13 glyphs from the original French
; release (French ROM 12DFF0-12E08B). The builder writes them into the matching
; font area beginning at ROM 12DFF0 in the US ROM.
;
; The stock text decoder normally sends $D3-$FF to the DTE path. Its compare
; immediate at ROM 0016F6 is changed from $D3 to $E1, making $D4-$E0 ordinary
; glyph codes while leaving $E1-$FF on the original DTE path.

org $C016F6
db $E1

; ---------------------------------------------------------------------------
; 4. Relocated WELCOME/help text
; ---------------------------------------------------------------------------
;
; C0:33B5 / ROM 0033B5 contains a 24-bit pointer to the help text.
; Stock: F0 33 C0 -> C0:33F0
; Patch: 00 80 ED -> ED:8000
;
; Relocating the help text removes the original 156-byte storage limit.
; $7F keeps the native line-control behavior and $00 terminates the resource.

org $C033B5
dl $ED8000

; The actual text bytes at ED:8000 are generated from WELCOME_1..WELCOME_4 in
; assets/game_select_text.csv; they are not duplicated here.
