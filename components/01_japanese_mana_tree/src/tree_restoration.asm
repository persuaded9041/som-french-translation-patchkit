; Secret of Mana (USA) - Japanese Mana Tree restoration
;
; Readable 65C816 source for the loader redirection used by the patch.
;
; build_patch.py embeds the validated assembled bytes directly, so an assembler
; is not required to build the patch.
;
; The exact helper was isolated from the working restoration behavior used by
; Secret of Mana Plus 2.1. Only the tree-resource redirection is retained here.
;
; Stock code at ROM 0x14CF6:
;
;     jml $7EAF0B
;
; becomes:
;
;     jml $EFF800
;
; $EF:F800 checks the current resource id. For resources other than $D2A9,
; it jumps directly back to the original $7EAF0B routine.
;
; For resource $D2A9, it redirects the image source to the Japanese resource
; copied to $EF:C000 and installs the decoder parameters required for the
; original full Mana Tree image.
;
; The binary builder deliberately keeps the known-good helper bytes rather
; than requiring an assembler. This file documents the code patch and provides
; a starting point for future clean-room reassembly/refactoring.

lorom

; Hook site is code copied/executed through the game's normal mapping.
; The builder patches the machine bytes at ROM offset $14CF6.

; Restored tree resource:
;   CPU $EF:C000
;   ROM $2FC000
;   size $3600

; Helper:
;   CPU $EF:F800
;   ROM $2FF800

; Important resource id:
;   $D2A9

; The current package uses the exact validated 160-byte helper blob.
; See build_patch.py for the byte-exact implementation.
