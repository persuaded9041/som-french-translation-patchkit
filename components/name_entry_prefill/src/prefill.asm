; Secret of Mana (USA) - editable default-name prefill
;
; Hook: C7:5039 replaces the final stock `STZ $A1CC / RTL` with a JML here.
; At this point the Name Entry screen/layout has already initialized $A159/$A15A,
; $A157 and $A156. We leave the ordinary editor in charge and insert each default
; character through the same stock routines used for manual input.
;
; Data records at C7:46D0 are eight bytes each:
;   length, token[0..6], padding
; token bits: bit7 = lowercase row, bits0-4 = alphabet index (A/a = 0).
;
; $A22B identifies boy/girl/sprite as 0/1/2. This component requires
; name_entry_extended; C7:5019 is still read live so the prefill does not
; duplicate the owning grid geometry. Lowercase is one row below uppercase.

org $C74630
name_entry_prefill_init:
    php
    rep #$10
    phx
    phy
    ldx $A159
    phx                         ; preserve the grid cursor word
    sep #$20
    stz $A1CC                  ; stock initial state: empty name
    stz $A1CD                  ; private loop counter during init only

    lda $A22B
    cmp #$03
    bcs .restore
    asl a
    asl a
    asl a
    tax                         ; 8-byte record per character
    lda.l name_entry_prefill_data,x
    and #$0F
    sta $A1CD
    beq .restore
    inx

.loop:
    lda.l name_entry_prefill_data,x
    pha
    and #$1F
    asl a
    asl a
    asl a
    clc
    adc #$13
    sta $A159                  ; column for this alphabet index
    pla
    bmi .lower
    lda.l $C75019              ; stock $60 / extended $50 uppercase row
    bra .row_done
.lower:
    lda.l $C75019
    clc
    adc #$10                   ; lowercase row
.row_done:
    sta $A15A

    phx
    jsl $C750E0                ; stock selector -> glyph tile pair
    bcs .skip_insert
    jsl $C75124                ; stock insertion/draw path
    inc $A157
    inc $A157
    inc $A1CC
.skip_insert:
    plx
    inx
    dec $A1CD
    bne .loop

.restore:
    stz $A1CD
    plx
    stx $A159                  ; restore ordinary grid cursor
    ply
    plx
    plp
    rtl

org $C746D0
name_entry_prefill_data:
    ; generated from assets/name_entry_defaults.json by build_patch.py
