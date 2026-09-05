; Secret of Mana (USA) - shared VWF decoded-text buffer bridge
; ============================================================
; Readable reference for shared/vwf_text_buffer.py, which is the executable
; canonical source. Components 05 and 06 install these hooks/helpers byte-for-byte.
;
; Stock parser buffer:   $7E:A1A4-$A1C4 (33 initialized bytes)
; Private VWF buffer:    $7E:9390-$93BB (44 bytes)
; Parser mode scratch:   $7E:9380 (0 stock, 1 intro, 2 dialogue)
;
; $A1C5/$A1C6 are live parser state and $A1C7 is renderer scratch, so the stock
; buffer must never be extended in place beyond $A1C4.
;
; The stock parser initializer is shared too:
;   $C0:1149 -> JSR $16B8 -> stacked return $114B : event engine
;   $C0:2359 -> JSR $16B8 -> stacked return $235B : GAME SELECT
; Only $114B may activate the private buffer.

hirom

!PARSER_MODE       = $9380
!PRIVATE_BUFFER    = $9390
!STOCK_BUFFER      = $A1A4
!INTRO_CONFIG      = $C74C80 ; $05 + 16-bit exclusive end pointer
!DIALOGUE_CONFIG   = $C74C84 ; $06 when component 06 is installed

org $C016B8
    jml shared_vwf_buffer_init

org $C016C6
    jsl shared_vwf_capacity
    nop #6

org $C017CE
    jml shared_vwf_parser_write

org $C018DE
    jml shared_vwf_previous_char

org $C743D0
shared_vwf_parser_write:
    pha
    lda !PARSER_MODE
    beq .stock
    pla
    sta !PRIVATE_BUFFER,x
    inx
    jml $C017D2
.stock:
    pla
    sta !STOCK_BUFFER,x
    inx
    jml $C017D2

org $C74AC0
shared_vwf_buffer_init:
    stz !PARSER_MODE
    rep #$20
    lda $01,s
    cmp #$114B
    sep #$20
    bne .stock_init

    ; Mode 1: component 05 translated intro event $0400.
    lda.l !INTRO_CONFIG
    cmp #$05
    bne .dialogue_check
    lda.l $001D03
    cmp #$CA
    bne .dialogue_check
    rep #$20
    lda.l $001D01
    cmp #$0C02
    bcc .dialogue_check16
    cmp.l !INTRO_CONFIG+1
    bcc .intro_active
.dialogue_check16:
    sep #$20
.dialogue_check:

    ; Mode 2: component 06 real event-engine text in stock banks C9/CA.
    lda.l !DIALOGUE_CONFIG
    cmp #$06
    bne .stock_init
    lda.l $001D03
    cmp #$C9
    beq .dialogue_active
    cmp #$CA
    bne .stock_init
.dialogue_active:
    lda #$02
    bra .private_init

.intro_active:
    sep #$20
    lda #$01
.private_init:
    sta !PARSER_MODE
    ldx #$0000
    lda #$80
.private_loop:
    sta !PRIVATE_BUFFER,x
    inx
    cpx #$002C
    bne .private_loop
    jml $C016C6

.stock_init:
    ldx #$0000
    lda #$80
.stock_loop:
    sta !STOCK_BUFFER,x
    inx
    cpx #$0021
    bne .stock_loop
    jml $C016C6

org $C74B40
shared_vwf_previous_char:
    sep #$20
    lda !PARSER_MODE
    beq .stock8
    rep #$20
    lda.l $7E9390,x
    jml $C018E2
.stock8:
    rep #$20
    lda.l $7EA1A4,x
    jml $C018E2

org $C74BC0
shared_vwf_capacity:
    lda !PARSER_MODE
    beq .stock
    cmp #$01
    beq .intro

    ; Dialogue: preserve remaining-line calculation, then grant six extra
    ; parser units. A fresh line therefore becomes 39 units = 38 glyphs plus
    ; the following control. Cap at $27.
    lda $A16A
    sec
    sbc $A181
    clc
    adc #$06
    cmp #$28
    bcc .store
    lda #$27
    bra .store
.intro:
    ; Runtime-validated component-05 behavior is preserved exactly.
    lda #$27
    bra .store
.stock:
    lda $A16A
    sec
    sbc $A181
.store:
    sta $A1CA
    rtl

; Runtime configuration bytes are component-owned rather than part of the
; byte-identical helper payload:
;   component 05: $C7:4C80 = $05, $C7:4C81-$4C82 = intro exclusive end
;   component 06: $C7:4C84 = $06
