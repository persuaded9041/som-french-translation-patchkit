; Secret of Mana (USA) - French four-row Name Entry navigation overlay
;
; Depends on name_entry_extended.  Adds the $80 fourth-row selector state.

hirom

org $C03583
name_row_up:
    jsr $324A
    lda $A15A
    sec
    sbc #$10
    cmp #$41
    bcs .commit
    lda #$80
.commit:
    jmp name_row_commit

org $C03595
name_row_down:
    jsr $324A
    lda $A15A
    clc
    adc #$10
    cmp #$81
    bcc name_row_commit
    lda #$50

name_row_commit:
    sta $A15A
    jsl $C7503D
    jsr $1BAA
    rts

; The French four-row layout adds a row above the generic three-row grid.
; ROM $075019 / SNES $C7:5019
org $C75019
db $50
