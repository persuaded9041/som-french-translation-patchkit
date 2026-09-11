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

; Direct-glyph/DTE routing is documented in name_dte.asm. Ordinary text
; still uses the $E1 base threshold; the relocated bank-$E4 Name Entry
; resource and PLAYER_NAME scratch source use $E8 so ♪, ° and ; stay direct.
