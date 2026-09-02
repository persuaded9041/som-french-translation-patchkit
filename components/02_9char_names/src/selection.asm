; Secret of Mana (USA) - Name Entry selection lookup

; Grid/lookup parameter used by the revised renderer.
; ROM $07502A / SNES $C7:502A
hirom

org $C7502A
db $0C

; Character lookup path. The selected encoded byte is ultimately loaded from
; the relocated Name Entry resource at $E4:4000,X.
; ROM $0750A6 / SNES $C7:50A6
org $C750A6
db $CC,$00,$BD,$00,$90,$DA,$38,$E9,$4E,$20,$4A,$AA,$E2,$20,$BF,$00,$40,$E4

; Selection-map origin. The visual grid was moved upward by one 16-pixel row.
; Keeping subtraction #$48 with selector states $50-$80 makes the selected
; character match the visible cursor row. #$38 caused A->a, a->accents, etc.
; ROM $0750E8 / SNES $C7:50E8
org $C750E8
db $48
