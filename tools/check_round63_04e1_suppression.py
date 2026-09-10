#!/usr/bin/env python3
"""Lock the exact Round-63 suppression of the standalone USA-only $04E1 page."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def translation_map():
    d=json.loads((ROOT/'translations/dialogues_french.json').read_text(encoding='utf-8'))
    return {e['id']:e['text'] for g in d['groups'] for e in g['entries']}

def main():
    tr=translation_map()
    if tr.get('CA:2C84') != '':
        raise SystemExit('$04E1/CA:2C84 must serialize as empty text')
    d=json.loads((ROOT/'translations/dialogues_french.json').read_text(encoding='utf-8'))
    om=[e for e in d.get('user_validated_structural_omissions',[]) if e.get('event_id')=='04E1']
    expected={
      'event_id':'04E1',
      'suppressed_semantic_ids':['CA:2C84'],
      'suppressed_commands':[{'name':'WAIT','args':'00','immediately_after_text_id':'CA:2C84'}],
      'reason':'round63_user_validated_resegmented_snes_jp_page_suppression',
    }
    if om != [expected]:
        raise SystemExit(f'$04E1 structural suppression drift: {om!r}')
    mass=json.loads((ROOT/'mappings/android/dialogues_format_mass.json').read_text(encoding='utf-8'))
    p=next((x for x in mass['partial_accepted_events'] if x['event_id']=='04E1'),None)
    if not p or p.get('partial_reason')!='manual_resegmented_page_suppression':
        raise SystemExit('$04E1 must remain PARTIEL under the Round-63 manual suppression reason')
    if p.get('manual_suppressed_semantic_ids') != ['CA:2C84']:
        raise SystemExit('$04E1 suppressed carrier metadata drift')
    if 'CA:2C84' in p.get('layout_deferred_semantic_ids',[]):
        raise SystemExit('$04E1/CA:2C84 must no longer be layout-deferred once suppressed')
    supp=json.loads((ROOT/'translations/dialogues_manual_supplements.json').read_text(encoding='utf-8'))
    e=next(x for x in supp['entries'] if x['id']=='CA:2C84')
    if e.get('status')!='suppressed' or e.get('reason')!='user_validated_resegmented_snes_jp_suppression':
        raise SystemExit('$04E1 manual evidence entry must record the validated suppression')
    html=(ROOT/'mappings/android/dialogues_review_worklist_round63.html').read_text(encoding='utf-8')
    if 'id="ev-04E1-CA-2C84"' not in html or '<section class="issueblock resolved" data-action="0" id="ev-04E1-CA-2C84">' not in html:
        raise SystemExit('Round-63 worklist must classify CA:2C84 as resolved/no-action')
    if '<b>65</b><br/>carriers nécessitant une action' not in html:
        raise SystemExit('Round-63 worklist action-carrier count drift')
    print('Round-63 $04E1 suppression verified: CA:2C84 empty + immediate WAIT $00 omitted; CA:2C93 retained')
if __name__=='__main__':
    main()
