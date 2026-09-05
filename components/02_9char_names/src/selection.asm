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

