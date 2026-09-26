#!/usr/bin/env python3
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.build.profile_overlay import build_profile_overlay  # noqa: E402

parser = argparse.ArgumentParser(description="Build the French VWF dialogue overlay")
parser.add_argument("rom", type=Path)
parser.add_argument("-o", "--output", type=Path, required=True)
args = parser.parse_args()
build_profile_overlay(PROJECT_ROOT / "components" / "default_vwf_dialogues", args.rom.resolve(), args.output)
print(f"IPS: {args.output}")
