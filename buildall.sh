#!/usr/bin/env sh
set -eu
ROM="${1:-roms/Secret of Mana (USA).sfc}"
rm -rf build/cache
python3 build.py "$ROM" all
python3 build.py "$ROM" --combine
