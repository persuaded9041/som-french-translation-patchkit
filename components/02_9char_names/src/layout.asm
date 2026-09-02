; Secret of Mana (USA) - four-row Name Entry layout

; Preserve the complete runtime-validated SoM Plus-derived control edit.
; ROM $07759D / SNES $C7:759D
org $C7759D
db $02,$06,$1E,$01,$C0,$04,$06,$1E,$81,$8A,$00,$02,$0A

; Private copy of the complete Name Entry layout script.
; Relative to the validated three-row script:
;   - character-window origin $02C0 -> $0240
;   - character-window height 6 -> 8 tile rows
;   - add draw command 08 AA 02 for the fourth character row
; The exact 110-byte payload is in src/patch_data.py.
; ROM $074E00 / SNES $C7:4E00
org $C74E00
; db ... generated from FOUR_ROW_LAYOUT_SCRIPT

; Keep both neighbouring validated $74EA pointers and redirect only the middle
; Name Entry layout pointer to our private script at C7:4E00.
; ROM $07781C / SNES $C7:781C
org $C7781C
dw $74EA,$4E00,$74EA
