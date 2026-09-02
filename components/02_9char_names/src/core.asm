; Secret of Mana (USA) - Name Entry core changes

; Maximum name length: 6 -> 9 characters.
; ROM $00319C / SNES $C0:319C
hirom

org $C0319C
db $09

; Redirect Name Edit Up and Down to our handlers in the old resource area.
; ROM $00334D / SNES $C0:334D
org $C0334D
dw $3583

; ROM $003363 / SNES $C0:3363
org $C03363
dw $3595

; Relocate the complete Name Entry character/text resource to expanded ROM.
; This frees C0:3583 for executable code.
; ROM $0033BE / SNES $C0:33BE
org $C033BE
dl $E44000

; French direct-glyph range $D4-$E0; $E1 remains the first DTE code.
; Glyph data itself is generated from shared/french_charset.
org $C016F6
    db $E1
