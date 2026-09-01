; Secret of Mana - final French opening helper
;
; Called from the existing fixed-width title renderer.
; Helper location: CPU $EE:9000 / ROM 0x2E9000.
; This avoids the intro VWF renderer at $C7:4285.
; A = encoded text byte
; Y = tilemap destination
; direct-page $02 = number of output cells
;
; $02 is a storage-only marker for the visible pair "e ".
; Literal periods are not special: "..." is stored as three $7B bytes.
;
; Pseudocode:
;
;   if A == $02:
;       emit $65       ; E
;       emit $60       ; blank
;       cell_count += 2
;       RTL
;
;   if A == $20:
;       A = $60        ; normal space -> blank tile
;
;   emit A
;   cell_count += 1
;   RTL
;
; The title arrangement loader is also redirected from the stock compressed
; block to CPU $EE:8000 (ROM 0x2E8000).
;
; This file is documentary. build_patch.py generates the exact helper bytes.
