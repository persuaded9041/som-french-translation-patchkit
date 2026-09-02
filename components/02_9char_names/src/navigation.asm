; Secret of Mana (USA) - four-row Name Entry navigation
;
; $A15A is the vertical selector state used by the naming screen:
;   $50 uppercase
;   $60 lowercase
;   $70 symbols
;   $80 French accents
;
; Up/Down changes the state by $10 and wraps across exactly those four rows.

; ROM $003583 / SNES $C0:3583
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

; ROM $003595 / SNES $C0:3595
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

; The screen originally initialized the vertical byte of X to $60 via
; LDX #$6013 / STX $A159. The four-row window was moved up by one row, so the
; initial state must be $50 to open on uppercase.
; ROM $075019 / SNES $C7:5019
org $C75019
db $50
