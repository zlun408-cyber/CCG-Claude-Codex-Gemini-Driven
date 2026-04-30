#!/usr/bin/env bash
DIR="$1"
cd "$DIR" || exit 1
STAMP_DIR="$DIR/.ccg/.pane_ids"
mkdir -p "$STAMP_DIR"
printf '%s\n' "${ITERM_SESSION_ID##*:}" > "$STAMP_DIR/gemini.session"
printf '\033]1337;SetBadgeFormat=R2VtaW5p\007'
python3 - <<'PY'
import tempfile
from pathlib import Path

warnings_file = Path(tempfile.gettempdir()) / "gemini-cli-warnings.txt"
warnings_file.write_text(
    "\n".join(
        [
            "Gemini 身份：前端开发 / UI-UX 负责人。",
            "职责：负责 UI、页面、组件、样式、响应式、可访问性和交互体验打磨。",
            "主要文件：src/components、src/pages、src/styles、*.css、以及 UI 相关 *.tsx。",
            "协作规则：等 Claude 冻结 API、数据、错误状态和设计契约后再实现；阻塞和完成情况回报给 Claude。",
        ]
    )
    + "\n",
    encoding="utf-8",
)
PY
exec gemini
