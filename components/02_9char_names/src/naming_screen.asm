; Secret of Mana (USA) - 9-character names and mixed-case naming screen
;
; Technical source map for the validated patch.
; File offsets assume the clean, unheadered USA ROM.
;
; build_patch.py is the canonical build implementation. This file documents
; the 65C816 changes and the generated resource layout in assembly-oriented
; form. The character pages and help text are authored in:
;
;   assets/naming_characters.txt
;   assets/naming_help.txt
;
; The builder encodes both files and writes the resulting resource at E4:4000.

; ---------------------------------------------------------------------------
; Name length
; ---------------------------------------------------------------------------

; File offset $00319C / SNES C0:319C
;
; Changes the maximum accepted name length to 9 characters.
org $C0319C
db $09

; ---------------------------------------------------------------------------
; Name Edit directional handlers
; ---------------------------------------------------------------------------
;
; The Name Edit input dispatch table contains separate handlers for each
; direction. In the original game, Up and Down both point to the generic
; no-operation handler at C0:3296. The patch redirects those two entries to
; new handlers placed in the old name-screen resource area.

; File offset $00334D - Name Edit / Up
org $C0334D
dw $3583

; File offset $003363 - Name Edit / Down
org $C03363
dw $3595

; ---------------------------------------------------------------------------
; Name Entry resource pointer
; ---------------------------------------------------------------------------
;
; The original Name Entry resource begins at C0:3583. The patch relocates it
; to expanded ROM space at E4:4000. This frees C0:3583 for executable code.

; File offset $0033BE
org $C033BE
dl $E44000

; ---------------------------------------------------------------------------
; Naming-page navigation code
; ---------------------------------------------------------------------------
;
; RAM $A15A contains the selector used by the character lookup path.
; The patch uses three values:
;
;   $60  uppercase page
;   $70  lowercase page
;   $80  symbols page
;
; Up subtracts $10 and wraps $60 -> $80.
; Down adds $10 and wraps $80 -> $60.
;
; JSR $324A preserves the stock directional-input processing.
; JSL $C7503D refreshes the naming-screen character content.
; JSR $1BAA executes the normal menu redraw/update path.

; File offset $003583 / SNES C0:3583
org $C03583
name_page_previous:
    jsr $324A
    lda $A15A
    sec
    sbc #$10
    cmp #$51
    bcs .store
    lda #$80
.store:
    jmp name_page_commit

; File offset $003595 / SNES C0:3595
org $C03595
name_page_next:
    jsr $324A
    lda $A15A
    clc
    adc #$10
    cmp #$81
    bcc name_page_commit
    lda #$60

name_page_commit:
    sta $A15A
    jsl $C7503D
    jsr $1BAA
    rts

; ---------------------------------------------------------------------------
; Internal ROM header
; ---------------------------------------------------------------------------
;
; The ROM is expanded from 2 MiB to 3 MiB. build_patch.py writes the updated
; ROM-size metadata and recalculates the SNES checksum after all source edits.
;
; For the canonical English sources, the resulting bytes at $00FFD7-$00FFDF
; match the validated reference patch exactly:
;
;   0C 03 01 C3 00 CB FC 34 03
;
; The checksum is not hard-coded for customized text builds.

; ---------------------------------------------------------------------------
; Bank C7 naming-screen changes
; ---------------------------------------------------------------------------

; File offset $07502A / SNES C7:502A
;
; Changes the naming-screen grid/lookup parameter used by the revised
; character renderer.
org $C7502A
db $0C

; File offset $0750A6 / SNES C7:50A6
;
; Reworks the character-selection lookup path. The final instruction is:
;
;   LDA.l $E44000,X
;
; which reads the selected encoded character from the relocated resource.
org $C750A6
db $CC,$00,$BD,$00,$90,$DA,$38,$E9,$4E,$20,$4A,$AA,$E2,$20,$BF,$00,$40,$E4

; File offset $07759D / SNES C7:759D
;
; Layout/control data required by the expanded naming grid.
org $C7759D
db $02,$06,$1E,$01,$C0,$04,$06,$1E,$81,$8A,$00,$02,$0A

; File offset $07781C / SNES C7:781C
;
; Associated table/pointer data used by the revised Name Entry layout.
org $C7781C
db $EA,$74,$9B,$75,$EA

; ---------------------------------------------------------------------------
; Generated Name Entry resource at E4:4000
; ---------------------------------------------------------------------------
;
; build_patch.py generates this block from text sources instead of including
; an opaque binary file.
;
; Layout:
;
;   +$0000  uppercase page    60 bytes
;   +$003C  lowercase page    60 bytes
;   +$0078  symbols page      60 bytes
;   +$00B4  help text         variable length
;
; Each character page contains 30 two-byte cells. A cell is encoded as:
;
;   80 <character-code>
;
; The builder automatically adds two leading blank cells, one trailing blank
; cell and the final 7F control cell. The 26 selectable entries themselves are
; read from assets/naming_characters.txt.
;
; The help text uses Secret of Mana's native text encoding. Source lines are
; read from assets/naming_help.txt. The builder inserts the original leading space on
; each display line and converts line boundaries to byte $7F.
;
; The canonical English sources generate 335 bytes and reproduce the original
; validated resource byte-for-byte.
