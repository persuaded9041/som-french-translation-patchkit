; Secret of Mana (USA) - French opening renderer helper
;
; This file documents the helper emitted byte-for-byte by build_patch.py.
; Startup-credit É is rendered separately by builder-generated title-code:
; stock E on the normal row plus acute tile $7D on the row above.
; Opening-font tile $7A therefore remains the stock Z.

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

; build_patch.py also relocates the title arrangement stream to $EE:A000
; and patches the title renderer to call this helper.

; Runtime-validated startup-credit overlay (builder-generated title-code/arrangement patch):
; stock credit call site -> JSR $BCED
; $BCED renders one overlay record at Y-$0040, then one normal record at Y.
; The credit-only CGRAM HDMA fade band is extended upward by one 8-pixel row
; (15/8 scanline split -> 7/16) while keeping the stock $8B5D fade state.
