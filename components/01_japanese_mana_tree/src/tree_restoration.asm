; Secret of Mana (USA) - Japanese Mana Tree restoration
; Documentation/source-map reference; build_patch.py is the canonical builder.

hirom

!TREE_RESOURCE = $EFC000
!TREE_HELPER   = $EFF800
!TREE_ID       = $D2A9

org $C14CF6
    jml !TREE_HELPER

org !TREE_RESOURCE
    incbin "../assets/mana_tree_jp.bin"

; Exact 160-byte loader helper emitted by build_patch.py.
org !TREE_HELPER
    db $08,$C2,$30,$48,$AF,$AC,$96,$7E,$C9,$A9,$D2,$F0,$06,$68,$28,$5C
    db $0B,$AF,$7E,$DA,$5A,$0B,$8B,$E2,$20,$A9,$7E,$48,$AB,$A9,$EF,$8D
    db $AD,$96,$8D,$C5,$96,$C2,$20,$A9,$00,$C0,$8D,$AA,$96,$8D,$C1,$96
    db $E2,$20,$A9,$0D,$8D,$53,$A0,$8D,$8A,$BE,$A9,$40,$8D,$F9,$BE,$A9
    db $80,$8D,$86,$BE,$8D,$C7,$BE,$A9,$F4,$8D,$23,$98,$A9,$F7,$8D,$13
    db $98,$A9,$3F,$8D,$0C,$D3,$A9,$F8,$8D,$5F,$D3,$A9,$08,$8D,$94,$D3
    db $C2,$20,$A9,$7B,$F8,$8D,$9B,$AD,$E2,$20,$A9,$EF,$8D,$9D,$AD,$C2
    db $30,$AB,$2B,$7A,$FA,$68,$28,$5C,$0B,$AF,$7E,$22,$14,$00,$C1,$48
    db $8B,$AF,$2E,$65,$7E,$C9,$60,$60,$F0,$03,$AB,$68,$6B,$DA,$5A,$A0
    db $A6,$64,$A2,$06,$65,$A9,$BF,$01,$54,$7E,$7E,$7A,$FA,$AB,$68,$6B
