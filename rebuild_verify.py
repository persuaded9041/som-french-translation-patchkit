#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE_SHA256='4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f'
COMPONENTS=[
 ('01_japanese_mana_tree', lambda d: d/'patch.ips'),
 ('02_9char_names', lambda d: d/'patch.ips'),
 ('03_game_select', lambda d: d/'patch.ips'),
 ('04_french_opening', lambda d: d/'patch.ips'),
 ('05_intro_vwf_french', lambda d: d/'patch.ips'),
]

def sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser(description='Rebuild every standalone component from source and compare it to packaged patch.ips.')
 ap.add_argument('rom',type=Path)
 args=ap.parse_args()
 if sha256(args.rom)!=BASE_SHA256: raise SystemExit('Wrong base ROM.')
 with tempfile.TemporaryDirectory(prefix='som_patchkit_') as td:
  tmp=Path(td); failures=[]
  for folder,get_patch in COMPONENTS:
   comp=ROOT/'components'/folder; out=tmp/folder
   if folder in ('01_japanese_mana_tree','04_french_opening','05_intro_vwf_french'):
    cmd=['python3',str(comp/'build_patch.py'),str(args.rom),'-o',str(out)]
   else:
    out.mkdir(parents=True,exist_ok=True)
    cmd=['python3',str(comp/'build_patch.py'),str(args.rom),'-o',str(out/'patch.ips')]
   result=subprocess.run(cmd,cwd=comp,capture_output=True,text=True)
   if result.returncode:
    failures.append((folder,'builder failed',result.stderr+result.stdout)); continue
   rebuilt=get_patch(out)
   ref=comp/'patch.ips'
   same=rebuilt.read_bytes()==ref.read_bytes()
   print(f'{"OK" if same else "MISMATCH":8} {folder}: {sha256(rebuilt)}')
   if not same: failures.append((folder,'byte mismatch',''))
  if failures:
   print('\nFailures:')
   for f in failures: print(' -',f[0],f[1],f[2])
   raise SystemExit(1)
 print('\nAll five builders reproduce their packaged runtime-validated IPS byte-for-byte.')

if __name__=='__main__':main()
