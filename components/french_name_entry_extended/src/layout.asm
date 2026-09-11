; Secret of Mana (USA) - French four-row Name Entry layout overlay
;
; Depends on name_entry_extended.  Expands the generic three-row keyboard
; ($02C0 / height 6) to the validated four-row geometry ($0240 / height 8)
; and draws the fourth row at 08 AA 02.

hirom

org $C74E00
    db $01,$40,$02,$08,$1E,$01,$C0,$04,$06,$1E,$81,$8A,$00,$02,$0A,$00
    db $03,$E8,$02,$04,$10,$03,$08,$2A,$01,$08,$AA,$01,$08,$2A,$02,$08
    db $AA,$02,$02,$E4,$00,$0C,$02,$64,$01,$10,$02,$E4,$01,$08,$01,$02
    db $00,$02,$07,$01,$C0,$04,$06,$1E,$00,$07,$6C,$00,$04,$1C,$03,$02
    db $44,$01,$10,$02,$64,$01,$08,$02,$44,$02,$14,$02,$64,$02,$0C,$01
    db $00,$00,$02,$09,$41,$08,$01,$02,$07,$41,$28,$01,$02,$07,$41,$08
    db $02,$02,$07,$41,$28,$02,$02,$07,$01,$40,$04,$08,$1E,$00
