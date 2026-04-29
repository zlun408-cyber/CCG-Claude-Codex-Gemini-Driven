#!/usr/bin/env bash
DIR="$1"
cd "$DIR" || exit 1
STAMP_DIR="$DIR/.ccg/.pane_ids"
mkdir -p "$STAMP_DIR"
printf '%s\n' "${ITERM_SESSION_ID##*:}" > "$STAMP_DIR/claude.session"
printf '\033]1337;SetBadgeFormat=Q2xhdWRl\007'
PROXY_PORT="${CCG_CLAUDE_PROXY_PORT:-51742}"
if ! /usr/bin/nc -z 127.0.0.1 "$PROXY_PORT" >/dev/null 2>&1; then
    nohup python3 "$DIR/.ccg/claude_gateway_proxy.py" --port "$PROXY_PORT" \
        > "$DIR/.ccg/claude_gateway_proxy.log" 2>&1 &
    sleep 0.5
fi

RUNTIME_SETTINGS="$DIR/.ccg/claude_runtime_settings.json"
python3 - "$RUNTIME_SETTINGS" "$PROXY_PORT" <<'PY'
import json
import sys

path, port = sys.argv[1], sys.argv[2]
settings = {
    "env": {
        # Claude Code gives settings env higher priority than shell env.
        # Keep this project-launched Claude pane on the compatibility proxy
        # even when ~/.claude/settings.json points directly at tokenhubpro.
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_MODEL": "gpt-5.5",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.5",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-5.5",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-5.5",
        "MAX_THINKING_TOKENS": "0",
        "CLAUDE_CODE_EFFORT_LEVEL": "unset",
        "CLAUDE_CODE_DISABLE_THINKING": "1",
        "DISABLE_THINKING": "1",
        "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
        "DISABLE_ADAPTIVE_THINKING": "1",
        "CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2": "1",
    }
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")
PY

export ANTHROPIC_BASE_URL="http://127.0.0.1:$PROXY_PORT"
export MAX_THINKING_TOKENS=0
export CLAUDE_CODE_EFFORT_LEVEL=unset
export ANTHROPIC_MODEL=gpt-5.5
export CLAUDE_CODE_DISABLE_THINKING=1
export DISABLE_THINKING=1
export CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1
export DISABLE_ADAPTIVE_THINKING=1
export CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2=1
exec claude --settings "$RUNTIME_SETTINGS" --model gpt-5.5
