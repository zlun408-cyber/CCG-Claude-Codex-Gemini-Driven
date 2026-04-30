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
import os
import sys
from pathlib import Path

path, port = sys.argv[1], sys.argv[2]
token = (
    os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    or os.environ.get("TOKENHUB_CODEX_API_KEY")
    or ""
)
if not token:
    try:
        user_settings = json.loads((Path.home() / ".claude" / "settings.json").read_text())
        user_env = user_settings.get("env", {})
        token = user_env.get("ANTHROPIC_API_KEY") or user_env.get("ANTHROPIC_AUTH_TOKEN") or ""
    except Exception:
        token = ""

env = {
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
    "ENABLE_TOOL_SEARCH": "false",
}
if token:
    # --bare reads API-key auth explicitly; keep the generated runtime file
    # ignored by git because it may contain a local token.
    env["ANTHROPIC_API_KEY"] = token
    env["ANTHROPIC_AUTH_TOKEN"] = token

settings = {
    "env": env
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
export ENABLE_TOOL_SEARCH=false
SYSTEM_PROMPT="$(
    {
        [ -f "$DIR/CLAUDE.md" ] && cat "$DIR/CLAUDE.md"
        printf '\n\n'
        [ -f "$DIR/.ccg/AGENTS.md" ] && cat "$DIR/.ccg/AGENTS.md"
    } 2>/dev/null
)"
exec claude --bare --settings "$RUNTIME_SETTINGS" --append-system-prompt "$SYSTEM_PROMPT" --model gpt-5.5
