#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
from build import COMPONENTS, patch_write_map, CHECKSUM_RANGE, MERGED_THRESHOLD_OFFSET

ROOT = Path(__file__).resolve().parent
EXPECTED = {
 '01_japanese_mana_tree':'424a15e1f08be4207054d99c83d0f69a5ec5cf2d9acf3160d7b35eeb35060027',
 '02_9char_names':'dc20f8994d78968863311543212dde5c9c8ee9befa97d58f79dd834d8156e77f',
 '03_game_select':'ede4084d40087fbaeb6622edeb9e976e4a70477ff1ba06cc5bafd610fb5b86d2',
 '04_french_opening':'ba9145ff516e48dfe838c1258bd9aa1841be6a2aa4c85e75af663f018313c14b',
 '05_intro_vwf_french':'36d419d9ad83e98cbc0b34ff41f11ef2941992ac223dc1cfc4d8b21ccdf37758',
}

def ranges(values):
    values=sorted(values)
    if not values: return []
    out=[]; start=prev=values[0]
    for x in values[1:]:
        if x==prev+1: prev=x
        else: out.append((start,prev)); start=prev=x
    out.append((start,prev)); return out


def main():
    maps={}
    ok=True
    for _,folder,_ in COMPONENTS:
        p=ROOT/'components'/folder/'patch.ips'
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        state='OK' if digest==EXPECTED[folder] else 'MISMATCH'
        print(f'{state:8} {folder}: {digest}')
        ok &= state=='OK'
        maps[folder]=patch_write_map(p.read_bytes())[0]

    print('\nOverlap audit (checksum bytes excluded from functional report):')
    functional_diff=[]
    for i,(_,a,_) in enumerate(COMPONENTS):
        for _,b,_ in COMPONENTS[i+1:]:
            common=set(maps[a])&set(maps[b])
            same={x for x in common if maps[a][x]==maps[b][x] and x not in CHECKSUM_RANGE}
            diff={x for x in common if maps[a][x]!=maps[b][x] and x not in CHECKSUM_RANGE}
            if same or diff:
                print(f'  {a} + {b}: same={len(same)}, different={len(diff)}')
                if same:
                    print('    identical:', ', '.join(f'0x{s:06X}-0x{e:06X}' if s!=e else f'0x{s:06X}' for s,e in ranges(same)))
                if diff:
                    print('    different:', ', '.join(f'0x{x:06X} (${maps[a][x]:02X}/${maps[b][x]:02X})' for x in sorted(diff)))
                    allowed=(a=='03_game_select' and b=='05_intro_vwf_french' and diff=={MERGED_THRESHOLD_OFFSET})
                    if not allowed: functional_diff.append((a,b,diff))
    if functional_diff:
        ok=False
        print('\nERROR: undeclared functional overlap detected.')
    else:
        print('\nOK: no undeclared functional overlap.')
        print('The GAME SELECT / intro-VWF glyph overlap is byte-identical and required for standalone operation.')
        print('Their decoder threshold overlap is explicitly resolved to $E6 by build.py.')
    raise SystemExit(0 if ok else 1)

if __name__=='__main__': main()
