; Secret of Mana (USA) - GAME SELECT translation support
; build_patch.py generates text/resources from assets/game_select_text.csv.

hirom

; Relocated 45-byte label resource at C7:4400.
org $C7780A
    dw $4400

; Current frame widths, derived by the builder from the translated labels.
org $C7756D
    db $07
org $C77572
    db $05
org $C77577
    db $06

; $D4-$E0 are direct French glyphs; $E1 remains the first DTE code.
; Glyph data is generated from shared/french_charset.
org $C016F6
    db $E1

; Relocated WELCOME/help text at ED:8000.
org $C033B5
    dl $ED8000
