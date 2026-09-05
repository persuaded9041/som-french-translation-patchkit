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

; GAME FILE/save-menu text is sourced from assets/game_file_text.csv.
; The stock C7:7340-C7:73BB resource is rebuilt at C7:4D40 so FILE can grow
; to "Fichier" without overwriting the following separator/data. Two states
; reference the same resource through the table entries below.
org $C77810
    dw $4D40
org $C77816
    dw $4D40

; Expand the FILE/Fichier frame from 6 cells ($03) to 8 cells ($04).
; This width is runtime-validated and keeps the following dynamic slot text outside the frame.
org $C77585
    db $04

; Dynamic GAME FILE level prefix: stock code writes the glyph for "L"
; directly into the menu text buffer in two rendering paths. Keep the
; one-cell layout and translate it to "N" (Niveau). This substitution is
; runtime-validated in both GAME FILE states.
org $C753C9
    db $A8
org $C75AF1
    db $A8

; C7:7805 Empty remains external to that resource and is patched in place.
; Save help is relocated to ED:8400 through the pointer at C0:33B8.
org $C033B8
    dl $ED8400

; No VWF is introduced for GAME FILE. The Fichier resource relocation and
; 8-cell frame are runtime-validated.
