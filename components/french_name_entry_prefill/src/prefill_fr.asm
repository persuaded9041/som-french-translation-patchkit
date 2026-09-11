; Secret of Mana (USA) - French editable default-name prefill overlay
;
; Dependency stack:
;   name_entry_extended -> french_name_entry_extended
;   name_entry_extended -> name_entry_prefill
;   name_entry_prefill + french_name_entry_extended -> french_name_entry_prefill
;
; This overlay keeps the generic prefill hook and stock insertion path. It
; replaces only the helper/token records so a default name can select a glyph
; from the French fourth row (needed by Popoï).
;
; Token format used by this overlay:
;   $00-$1F : uppercase row, alphabet index in bits0-4
;   $80-$9F : lowercase row, alphabet index in bits0-4
;   $C0-$DF : French extension row, index in bits0-4
;
; The actual French extension row is owned by french_name_entry_extended.
; The helper reads C7:5019 live ($50 under the French four-row overlay), then
; adds $10 for lowercase or $30 for the fourth row.
