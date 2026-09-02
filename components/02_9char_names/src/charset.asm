; Secret of Mana (USA) - naming-safe French charset
;
; This screen safely uses the original French-ROM direct range $D4-$E0:
;   D4 Ç   D5 à   D6 â   D7 ç   D8 é   D9 è   DA ê
;   DB ë   DC î   DD ï   DE ô   DF ù   E0 û
;
; $E1-$E5 are intentionally not overwritten here because those slots are still
; used by graphics on the Name Entry screen.

; Direct glyph / DTE threshold: values below $E1 are direct glyphs.
; ROM $0016F6 / SNES $C0:16F6
org $C016F6
db $E1

; Glyph bitmap bytes for $D4-$E0 are generated from the shared canonical asset:
;   shared/french_charset/french_glyphs.png
; and written at ROM $12DFF0-$12E08B by build_patch.py.
