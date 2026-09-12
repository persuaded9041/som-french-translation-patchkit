; Context-sensitive dialogue direct/DTE boundary
; ==============================================
; Readable reference for shared/dialogue/dte.py (executable canonical source).
;
; `vwf_dialogues` / `french_dialogues` replace stock CMP #$D3 / BCS upper_dte at $C0:16F5 with
; a JML here. The helper preserves the validated intro profile:
;   non-event parser / GAME SELECT -> $E6
;   event $0400                  -> $E6
;   ordinary event dialogue      -> $E8 when $C7:4C85 == $E8
;
; $E6/$E7 therefore remain intro DTE tokens but are direct ° / ; glyphs in
; dialogue. $D3 is direct ♪ under either full-French boundary.

hirom

!INTRO_CONFIG       = $C74C80
!DIALOGUE_DTE_CFG   = $C74C85

org $C016F5
    jml dialogue_dte_route

org $C74570
dialogue_dte_route:
    ; See dialogue_dte.py for generated machine code. When `vwf_dialogues` is
    ; active, the helper first trusts the shared parser mode selected at
    ; $C0:16B8: mode 2 -> dialogue/$E8, mode 1 -> intro/$E6. Mode 0 and
    ; `french_dialogues` standalone builds fall back to caller/event checks. It JMLs
    ; to stock $C0:16F9 for direct/control processing or $C0:170D for DTE.
