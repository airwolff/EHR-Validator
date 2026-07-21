#!/usr/bin/env bash
# present.sh — the driver for the one-take recording.
# Run setup.sh FIRST (off camera). Then start this, press record, swipe to the deck.
# Each demo waits on a bare Enter so nothing instructional shows on camera.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../.."
gate(){ read -r _; clear; }

clear
gate                 # Enter to start Demo 1 (slide 3)
"$HERE/demo1.sh"
gate                 # Enter to start Demo 2 (slide 4)
"$HERE/demo2.sh"
gate                 # Enter to start Demo 3 (slide 5)
"$HERE/demo3.sh"
