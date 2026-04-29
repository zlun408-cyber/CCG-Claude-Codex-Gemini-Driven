#!/usr/bin/env bash
DIR="$1"
cd "$DIR" || exit 1
STAMP_DIR="$DIR/.ccg/.pane_ids"
mkdir -p "$STAMP_DIR"
printf '%s\n' "${ITERM_SESSION_ID##*:}" > "$STAMP_DIR/gemini.session"
printf '\033]1337;SetBadgeFormat=R2VtaW5p\007'
exec gemini
