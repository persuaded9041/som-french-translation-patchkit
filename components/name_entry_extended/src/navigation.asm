; Secret of Mana (USA) - three-row Name Entry navigation
;
; $A15A is the vertical selector state used by the naming screen:
;   $60 uppercase
;   $70 lowercase
;   $80 symbols
;
; Up/Down changes the state by $10 and wraps across exactly those three rows.

; ROM $003583 / SNES $C0:3583
hirom

org $C03583
name_row_up:
    jsr $324A
    lda $A15A
    sec
    sbc #$10
    cmp #$51
    bcs .commit
    lda #$80
.commit:
    jmp name_row_commit

; ROM $003595 / SNES $C0:3595
org $C03595
name_row_down:
    jsr $324A
    lda $A15A
    clc
    adc #$10
    cmp #$81
    bcc name_row_commit
    lda #$60

name_row_commit:
    sta $A15A
    jsl $C7503D
    jsr $1BAA
    rts

; The generic three-row keyboard intentionally retains the stock initial
; vertical selector $60. The French four-row overlay moves the first row to
; $50 and owns that override.
