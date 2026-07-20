#!/usr/bin/env bash
# present.sh — the driver for the one-take recording.
# It tells you where you are and runs the right demo when you swipe to the terminal.
# Run setup.sh FIRST (off camera), then start this, then press record.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"   # absolute path to this folder, however it was invoked
cd "$HERE/../.."                        # repo root

banner(){ printf '\n\033[1;36m========================================================\n%s\n========================================================\033[0m\n' "$1"; }
wait_enter(){ printf '\033[1;33m%s\033[0m' "$1"; read -r _; }

clear
banner "PRESENT — one-take driver"
cat <<'TXT'
Before you go on camera:
  • setup.sh has been run (DB is at the clean 7-fixture state)
  • deck is full-screen on the OTHER desktop, this terminal on THIS one
  • Do Not Disturb is on

This script pauses each time it's the terminal's turn. Swipe here, press Enter,
narrate over the output. Swipe back to the deck when it says so.
TXT
wait_enter $'\nPress Enter once you have pressed RECORD and are ready to begin...'

banner "SLIDES 1-2  (deck)  —  Objective, then Architecture"
echo "Present slides 1 and 2 on the deck. Do NOT swipe here yet."
echo "When you reach SLIDE 3 and have set up the wrong-patient record,"
wait_enter $'SWIPE to this terminal and press Enter to run DEMO 1 (slide 3)...'

banner "DEMO 1  (slide 3)  —  the night shift finds what rules can't"
"$HERE/demo1.sh"
echo
echo ">>> Done. SWIPE BACK to the deck and present SLIDE 4."
wait_enter $'When slide 4 reaches its demo, SWIPE here and press Enter for DEMO 2...'

banner "DEMO 2  (slide 4)  —  the same test, five times"
"$HERE/demo2.sh"
echo
echo ">>> Done. SWIPE BACK to the deck and present SLIDE 5."
wait_enter $'When slide 5 reaches its demo, SWIPE here and press Enter for DEMO 3...'

banner "DEMO 3  (slide 5)  —  the whole month at once"
"$HERE/demo3.sh"
echo
banner "DEMOS DONE"
echo ">>> SWIPE BACK to the deck for SLIDES 6, 7, 8, 9."
echo ">>> Stop the recording after slide 9 (the repo URL)."
echo
