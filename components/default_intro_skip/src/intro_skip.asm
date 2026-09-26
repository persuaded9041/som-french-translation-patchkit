; Secret of Mana (USA) - validated hold-R new-game introduction skip
; Readable mirror only; build_patch.py is the canonical emitter.
;
; Runtime-validated behavior:
;   - synchronized pad state: $7E:0042, R = bit $10
;   - continuous hold for 120 normal-loop ticks
;   - release before zero resets timer to $FFFF; short presses do not accumulate
;   - completed timer ($0000) is sticky until a safe commit point consumes it
;   - normal translated-intro scope only: $CA:0C02-$0E81
;   - final $1D $7F Mode-7/flyover phase at $CA:0E82 is intentionally excluded
;
; Timer state at $7E:938A (16-bit):
;   $FFFF inactive
;   $0001-$FFFE counting
;   $0000 completed / pending skip

!PAD1           = $7E0042
!R_MASK         = $10
!TIMER          = $7E938A
!HOLD_TICKS     = $0078
!INTRO_START    = $0C02
!TEXT_START     = $0C0C
!PARSER_START   = $0C54
!INTRO_END      = $0E82

org $C0012C
    jml intro_skip_text_observer

org $C016EA
    jml intro_skip_parser_commit

org $C2C786
    jml intro_skip_normal_loop

org $CAFFC0
intro_skip_tail:
    db $51                  ; TEXT_CLOSE
    db $18,$00              ; waterfall room $0000
    db $2A,$F8              ; balance intro $29 F8
    db $11,$06,$00          ; JUMP $0106

org $CAFFC8
intro_skip_parser_commit:
    php
    sep #$20
    rep #$10
    lda.l $001D03
    cmp #$CA
    bne .stock8

    rep #$20
    cpy #!PARSER_START
    bcc .stock16
    cpy #!INTRO_END
    bcs .stock16
    lda.l !TIMER
    cmp #$0000
    bne .stock16

    lda #$FFFF              ; consume completed request
    sta.l !TIMER
    ldy #$FFC0              ; continue decoding at private tail

.stock16:
    sep #$20
.stock8:
    plp
    lda $0000,y             ; displaced stock bytes
    iny
    jml $C016EE

; Aggregate-only compatibility helper. The standalone component still hooks
; C0:16EA directly to CA:FFC8. When vwf_dialogues is also selected, the build
; merge rule rewrites C0:16EA to this dispatcher.
org $ED73C0
intro_skip_parser_dispatcher:
    lda.l $7E9380
    cmp #$02
    beq .dialogue
    jml intro_skip_parser_commit
.dialogue:
    jml $ED7500

org $ED7400
intro_skip_normal_loop:
    sep #$20                ; displaced stock bytes
    rep #$10
    php

    lda $D3
    cmp #$CA
    bne .done
    rep #$20
    lda $D1
    cmp #!INTRO_START
    bcc .done16
    cmp #!INTRO_END
    bcs .done16

    lda.l !TIMER
    cmp #$0000
    beq .expired

    sep #$20
    lda.l !PAD1
    and #!R_MASK
    bne .held

    rep #$20                ; release cancels current hold
    lda #$FFFF
    sta.l !TIMER
    sep #$20
    bra .done

.held:
    rep #$20
    lda.l !TIMER
    cmp #$FFFF
    bne .counting
    lda #!HOLD_TICKS        ; first held observation arms full duration
    sta.l !TIMER
    sep #$20
    bra .done

.counting:
    dec a
    sta.l !TIMER
    cmp #$0000
    bne .done16

.expired:
    sep #$20
    lda $D0
    cmp #$82                ; only stock timed WAIT is safe here
    bne .done
    rep #$20
    lda #$FFFF              ; consume completed request
    sta.l !TIMER
    sep #$20
    lda #$C0
    sta $D1
    lda #$FF
    sta $D2
    lda #$CA
    sta $D3
    lda #$01
    sta $4F                 ; let untouched stock WAIT expire naturally
    bra .done

.done16:
    sep #$20
.done:
    plp
    jml $C2C78A

org $ED7488
intro_skip_text_observer:
    php                     ; complete displaced stock prologue
    sep #$20
    rep #$10

    lda.l $001D03
    cmp #$CA
    bne .done
    rep #$20
    lda.l $001D01
    cmp #!TEXT_START
    bcc .done16
    cmp #!INTRO_END
    bcs .done16

    ; Fresh WRAM begins at zero; establish explicit inactive sentinel once.
    cmp #!TEXT_START
    bne .initialized
    lda.l !TIMER
    cmp #$0000
    bne .initialized
    lda #$FFFF
    sta.l !TIMER

.initialized:
    lda.l !TIMER
    cmp #$0000              ; completed request stays sticky
    beq .done16

    sep #$20
    lda.l !PAD1
    and #!R_MASK
    bne .held

    rep #$20                ; release cancels current hold
    lda #$FFFF
    sta.l !TIMER
    sep #$20
    bra .done

.held:
    rep #$20
    lda.l !TIMER
    cmp #$FFFF
    bne .done16             ; C2 owns decrement once armed
    lda #!HOLD_TICKS
    sta.l !TIMER
    sep #$20
    bra .done

.done16:
    sep #$20
.done:
    jml $C00131
