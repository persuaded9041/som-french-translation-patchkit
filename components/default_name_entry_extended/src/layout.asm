; Secret of Mana (USA) - three-row extended Name Entry layout

hirom

; SoM Plus-derived control bytes used by the widened 9-character Name Entry.
org $C7759D
    db $02,$06,$1E,$01,$C0,$04,$06,$1E,$81,$8A,$00,$02,$0A

; Private three-row keyboard layout.  This is the validated four-row script
; with the fourth draw command removed and the keyboard window restored to the
; three-row $02C0 / height-6 geometry.
org $C74E00
    db $01,$C0,$02,$06,$1E,$01,$C0,$04,$06,$1E,$81,$8A,$00,$02,$0A,$00
    db $03,$E8,$02,$04,$10,$03,$08,$2A,$01,$08,$AA,$01,$08,$2A,$02,$02
    db $E4,$00,$0C,$02,$64,$01,$10,$02,$E4,$01,$08,$01,$02,$00,$02,$07
    db $01,$C0,$04,$06,$1E,$00,$07,$6C,$00,$04,$1C,$03,$02,$44,$01,$10
    db $02,$64,$01,$08,$02,$44,$02,$14,$02,$64,$02,$0C,$01,$00,$00,$02
    db $09,$41,$08,$01,$02,$07,$41,$28,$01,$02,$07,$41,$08,$02,$02,$07
    db $41,$28,$02,$02,$07,$01,$40,$04,$08,$1E,$00

org $C7781C
    dw $74EA,$4E00,$74EA
