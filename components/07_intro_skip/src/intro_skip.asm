; Secret of Mana (USA) - skippable new-game introduction
; Documentation/source-map reference; build_patch.py is the canonical emitter.
; Hold R for 120 NMI frames (~2 s) to skip directly to the waterfall with
; the stock end-of-intro cleanup minus the Mode 7 world-map flyover. The hold
; is non-blocking, so the introduction continues while R is held.
;
; C0:012C is runtime-validated as an execution point during the intro.
; The intro is identified exactly like component 05: bank $CA and live event
; pointer in $0C02-$0E8A.
;
; Non-blocking state:
;   $7E:938A = frame at which the current R hold began
;   $7E:938B = hold-active flag
;
; These bytes are unused by component 05's $CA intro renderer. Component 06
; uses the same scratch neighborhood only under mutually exclusive $C9 scope.
; State is explicitly initialized at the start of event $0400 and cleared when
; R is released or the skip fires. A tiny NMI hook also clears HOLD_ACTIVE on
; release every frame so a release missed by the event-engine hook cannot make
; separate presses accumulate.

!INTRO_START      = $0C02
!INTRO_END        = $0E8B
!HOLD_FRAMES      = $78
!HOLD_START_FRAME = $7E938A
!HOLD_ACTIVE      = $7E938B

org $C0012C
    jml intro_skip_input_hook

org $C0AC34
    jml intro_skip_nmi_release_hook

org $CAFFC0
intro_skip_event:
    db $51
    db $18,$00
    db $2A,$F8
    db $11,$06,$00

org $ED7400
intro_skip_input_hook:
    php
    sep #$20
    rep #$10

    lda.l $001D03
    cmp #$CA
    bne .done8

    rep #$20
    lda.l $001D01

    cmp #!INTRO_START
    bne .range_check
    sep #$20
    lda #$00
    sta.l !HOLD_ACTIVE
    sta.l !HOLD_START_FRAME
    rep #$20
    lda.l $001D01

.range_check:
    cmp #!INTRO_START
    bcc .done16
    cmp #!INTRO_END
    bcs .done16

    sep #$20
    lda.l $004218
    and #$10
    beq .released

    lda.l !HOLD_ACTIVE
    bne .holding

    lda.l $0000F4
    sta.l !HOLD_START_FRAME
    lda #$01
    sta.l !HOLD_ACTIVE
    bra .done8

.holding:
    lda.l $0000F4
    sec
    sbc.l !HOLD_START_FRAME
    cmp #!HOLD_FRAMES
    bcc .done8

    lda #$00
    sta.l !HOLD_ACTIVE
    rep #$20
    lda #$FFC0
    sta.l $001D01
    sep #$20
    lda #$CA
    sta.l $001D03
    bra .done8

.released:
    lda #$00
    sta.l !HOLD_ACTIVE
    bra .done8

.done16:
    sep #$20
.done8:
    jml $C00131


org $ED7490
intro_skip_nmi_release_hook:
    ; C0:AC34 runs every NMI immediately after INC $00F4.
    ; Clear only the active flag when R is physically released; do not pause
    ; or otherwise alter the intro.
    lda.l !HOLD_ACTIVE
    beq .stock
    lda.l $004218
    and #$10
    bne .stock
    lda #$00
    sta.l !HOLD_ACTIVE

.stock:
    ; Restore the stock instructions overwritten by the JML at C0:AC34.
    lda $000E
    and $000F
    jml $C0AC3A
