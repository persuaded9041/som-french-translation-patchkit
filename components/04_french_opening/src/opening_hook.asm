; Secret of Mana (USA) - French opening renderer helper
;
; This file documents the helper emitted byte-for-byte by build_patch.py.
; The startup-credit É does not require helper code: opening_credits.csv maps
; it to tile $7A, whose artwork lives directly in assets/opening_font.png.
; $7A was the opening font's Z slot and is reserved by this component.

hirom

!COMPACT_E_SPACE = $02
org $EE9000
opening_char:
    cmp #!COMPACT_E_SPACE
    beq .e_space

    cmp #$20
    bne .emit
    lda #$60

.emit:
    sta $0000,y
    iny
    iny
    inc $02
    rtl

.e_space:
    lda #$65
    sta $0000,y
    iny
    iny
    lda #$60
    sta $0000,y
    iny
    iny
    inc $02
    inc $02
    rtl

; build_patch.py also relocates the compressed title arrangement to $EE:8000
; and patches the title renderer to call this helper.
