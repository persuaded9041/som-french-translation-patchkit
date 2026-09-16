; Shared VWF stock-outline preparation.
; Executable canonical source: vwf_outline.py
;
; Stock $C0:162C uses ROL at $C0:163D after the previous row's LSR has left
; carry set/clear from that prior row. ASL prevents that carry from becoming a
; pixel in the next row. `vwf_intro`, `vwf_dialogues` and `vwf_ui` install this
; same one-byte patch.

hirom

org $C0163D
    asl
