#!/usr/bin/env python3
"""
iTerm2 Multi-Agent Chat Bridge
===============================
放到任意项目目录下即可使用。通过 iTerm2 Python API 实现
Claude Code / Codex / Gemini / Codex2 四个 pane 之间的双向通信。

依赖: pip3 install iterm2

用法:
  python3 iterm_chat.py list                      列出所有 pane
  python3 iterm_chat.py read <agent> [N]          读取 agent 最近内容 (默认 40)
  python3 iterm_chat.py send <agent> <text>       发送原始文本 (无 Enter)
  python3 iterm_chat.py say <agent> <text>        发送消息并提交 (自动 Enter)
  python3 iterm_chat.py ask <agent> <question>    发送问题, 等待回复, 打印结果

  <agent> 可以是: claude / codex / gemini / codex2 / 1 / 2 / 3 / 4

示例:
  python3 iterm_chat.py say codex "帮我检查 main.py 有没有 bug"
  python3 iterm_chat.py say codex2 "运行回归测试并汇报结果"
  python3 iterm_chat.py ask gemini "解释一下这个正则: ^(?=.*[A-Z]).{8,}$"
  python3 iterm_chat.py read codex
  python3 iterm_chat.py read codex2 25

注意:
  - Gemini 的 TUI 会吞掉紧跟文本发送的 Enter, 所以文本和 Enter 之间有 0.3s 延迟
  - Claude/Codex 读取当前屏幕缓冲区；Gemini 读取其 chat jsonl 历史，避免 TUI 不显示历史导致误判
  - 如果 Gemini 进入了 shell mode, 先发送 Escape 退出: ./iterm_chat.py send gemini $'\\x1b'
"""

import asyncio
import iterm2
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# Agent 识别: 关键词 -> pane 匹配规则
# ============================================================
AGENT_KEYWORDS = {
    "claude": ["claude"],
    "codex":  ["codex"],
    "gemini": ["gemini"],
    "codex2": ["codex2"],
}

AGENT_BADGES = {
    "claude": ["claude"],
    "codex": ["codex"],
    "gemini": ["gemini"],
    "codex2": ["codex2"],
}

AGENT_ALIASES = {
    "1": "claude", "2": "codex", "3": "gemini", "4": "codex2",
    "c": "claude", "cx": "codex", "g": "gemini", "cx2": "codex2",
}


def resolve_agent(name: str) -> str:
    """将用户输入的 agent 名解析为标准名 (claude/codex/gemini/codex2)。"""
    key = name.lower().strip()
    if key in AGENT_ALIASES:
        return AGENT_ALIASES[key]
    if key in AGENT_KEYWORDS:
        return key
    # 模糊匹配
    for agent_name in AGENT_KEYWORDS:
        if key in agent_name or agent_name.startswith(key):
            return agent_name
    return key


def _classify_sessions(sessions):
    """对一组 sessions 按名称分类，返回 {agent_name: (pane_index, session)}。"""
    agents = {}

    def session_text(session):
        parts = [session.name.lower()]
        badge = getattr(session, "badge", None)
        if badge:
            parts.append(str(badge).lower())
        return " ".join(parts)

    for i, s in enumerate(sessions):
        pane = i + 1
        text = session_text(s)

        if "codex2" in text and "codex2" not in agents:
            agents["codex2"] = (pane, s)
            continue
        if "claude" in text and "claude" not in agents:
            agents["claude"] = (pane, s)
            continue
        if "gemini" in text and "gemini" not in agents:
            agents["gemini"] = (pane, s)
            continue
        if "codex" in text and "codex" not in agents:
            agents["codex"] = (pane, s)
            continue

    return agents


def _get_own_session_id():
    """从环境变量获取当前进程所在的 iTerm2 session ID。"""
    env = os.environ.get("ITERM_SESSION_ID", "")
    # 格式: w3t0p0:UUID  → 取冒号后面的 UUID
    if ":" in env:
        return env.split(":", 1)[1]
    return env


def _load_saved_sessions():
    """读取 .ccg/.sessions 文件，返回 {agent_name: session_id}。

    这个文件由 start 脚本在启动时生成，记录了当前团队窗口的精确 session ID。
    """
    candidates = []

    # 最高优先：与当前脚本同目录的 .sessions。
    # 这样即使从子目录或绝对路径执行 /path/to/project/.ccg/iterm_chat.py，
    # 也能读取到该项目自己的 session 记录。
    try:
        script_dir = Path(__file__).resolve().parent
        candidates.append(script_dir / '.sessions')
    except Exception:
        pass

    # 兼容旧行为：从 CWD 往上找 .ccg/.sessions。
    try:
        cwd = Path.cwd().resolve()
        for base in (cwd, *cwd.parents):
            candidates.append(base / '.ccg' / '.sessions')
    except Exception:
        pass

    path = None
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            path = candidate
            break

    if path is None:
        return {}

    result = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if ':' in line:
                agent, sid = line.split(':', 1)
                result[agent.strip()] = sid.strip()
    return result


def _project_root():
    """Return the project root that owns this .ccg directory."""
    try:
        return Path(__file__).resolve().parent.parent
    except Exception:
        return Path.cwd().resolve()


def _gemini_project_dir():
    """Locate Gemini's per-project tmp directory for this project."""
    root = _project_root().resolve()
    tmp_root = Path.home() / ".gemini" / "tmp"

    if tmp_root.exists():
        for candidate in tmp_root.iterdir():
            marker = candidate / ".project_root"
            if not marker.exists():
                continue
            try:
                marked = Path(marker.read_text().strip()).resolve()
            except Exception:
                continue
            if marked == root:
                return candidate

    slug = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-")
    return tmp_root / slug


def _latest_gemini_chat_file():
    chat_dir = _gemini_project_dir() / "chats"
    if not chat_dir.exists():
        return None
    files = list(chat_dir.glob("session-*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _event_text(event):
    content = event.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return ""


def _event_epoch(event):
    value = event.get("timestamp")
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _read_gemini_events():
    path = _latest_gemini_chat_file()
    if path is None:
        return []

    events = []
    with open(path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or "$set" in event:
                continue
            if event.get("type") in ("user", "gemini", "info"):
                events.append(event)
    return events


def _format_gemini_events(limit=20):
    events = _read_gemini_events()[-limit:]
    if not events:
        return None

    lines = []
    for event in events:
        ts = event.get("timestamp", "")
        clock = ts[11:19] if len(ts) >= 19 else "--:--:--"
        role = event.get("type", "unknown")
        text = _event_text(event).strip()
        if text:
            lines.append(f"[{clock}] {role}: {text}")
    return "\n\n".join(lines) if lines else None


async def _wait_for_gemini_response(started_at, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for event in reversed(_read_gemini_events()):
            if event.get("type") != "gemini":
                continue
            if _event_epoch(event) >= started_at - 1:
                text = _event_text(event).strip()
                if text:
                    return text
        await asyncio.sleep(1)
    return None


async def _find_team_window(connection, target_agent=None):
    """扫描所有 iTerm2 窗口，找到包含 Claude+Codex+Gemini+Codex2 的团队窗口。

    策略 (按优先级):
    0. 最高优先：通过 .ccg/.sessions 保存的精确 session ID 匹配
    1. 次优先：包含自身 session 的窗口（自己所在的窗口就是团队窗口）
    2. 标准团队窗口：4 pane 且 4 个名字都匹配
    3. 有目标 agent 的窗口 +20 分
    4. 位置兜底保证 4 pane 总能匹配满
    """
    app = await iterm2.async_get_app(connection)

    # 策略 0: 通过保存的 session ID 精准匹配
    saved = _load_saved_sessions()
    if saved:
        seen_saved = {}
        for window in app.windows:
            for tab in window.tabs:
                agents = {}
                for i, s in enumerate(tab.sessions):
                    for agent_name, sid in saved.items():
                        if sid in s.session_id or s.session_id.endswith(sid):
                            agents[agent_name] = (i + 1, s)
                            seen_saved[agent_name] = s.session_id
                            break
                if len(agents) == len(saved):
                    return tab, agents

        missing = [agent for agent in saved if agent not in seen_saved]
        print("Error: Saved CCG sessions were not found in iTerm2.")
        print("  The .ccg/.sessions file is stale, or the CCG iTerm window was closed.")
        if missing:
            print(f"  Missing agents: {', '.join(missing)}")
        print("  Fix: run ./start again from the project root to recreate the team window.")
        sys.exit(1)

    # 策略 1+: 原有的名称 + 位置匹配逻辑
    own_sid = _get_own_session_id()

    best = None          # (score, tab, agents_dict)

    for window in app.windows:
        for tab in window.tabs:
            sessions = tab.sessions
            agents = _classify_sessions(sessions)

            # 基础分
            if len(sessions) == 4 and len(agents) == 4:
                score = 100
            elif len(agents) >= 3:
                score = 60 + len(agents) * 5
            elif len(agents) >= 2:
                score = 30 + len(agents) * 5
            elif len(agents) == 1:
                score = 10
            else:
                continue

            # 自己所在的窗口加大分
            if own_sid:
                for s in sessions:
                    if own_sid in s.session_id:
                        score += 200
                        break

            # 目标 agent 加分
            if target_agent and target_agent in agents:
                score += 20

            if best is None or score > best[0]:
                best = (score, tab, agents)

    if best:
        return best[1], best[2]

    # fallback: current_window
    window = app.current_window
    if window:
        tab = window.current_tab
        agents = _classify_sessions(tab.sessions)
        return tab, agents

    print("Error: No iTerm2 window found")
    sys.exit(1)


async def get_sessions(connection):
    """兼容旧接口：返回团队窗口的 sessions 列表。"""
    tab, _ = await _find_team_window(connection)
    return tab.sessions


async def detect_agents(connection):
    """扫描团队窗口所有 pane, 返回 {agent_name: (pane_index, session)} 映射。"""
    _, agents = await _find_team_window(connection)
    return agents


async def find_session(connection, agent_name: str):
    """根据 agent 名找到对应的 pane_index 和 session。"""
    resolved = resolve_agent(agent_name)
    tab, agents = await _find_team_window(connection, target_agent=resolved)
    if resolved in agents:
        return agents[resolved]
    # fallback: 尝试用数字索引
    sessions = tab.sessions
    try:
        idx = int(resolved) - 1
        if 0 <= idx < len(sessions):
            return (idx + 1, sessions[idx])
    except ValueError:
        pass
    print(f"Error: Agent '{agent_name}' not found in any iTerm2 tab")
    print(f"  Available: {', '.join(agents.keys()) if agents else 'none detected'}")
    sys.exit(1)


# ============================================================
# 核心操作
# ============================================================

async def cmd_list(connection):
    sessions = await get_sessions(connection)
    agents = await detect_agents(connection)
    # 反向映射: pane_index -> agent_name
    pane_to_agent = {v[0]: k for k, v in agents.items()}
    print("iTerm2 Panes:")
    for i, s in enumerate(sessions):
        tag = pane_to_agent.get(i + 1, "?")
        print(f"  [{tag:>6}] Pane {i+1}: {s.name}")


async def cmd_read(connection, agent_name: str, last_n: int = 40):
    resolved = resolve_agent(agent_name)
    if resolved == "gemini":
        transcript = _format_gemini_events(last_n)
        if transcript:
            print(transcript)
            return

    pane, session = await find_session(connection, agent_name)
    content = await session.async_get_screen_contents()
    n = content.number_of_lines
    start = max(0, n - last_n)
    lines = []
    for i in range(start, n):
        lines.append(content.line(i).string)
    print("\n".join(lines))


async def cmd_send(connection, agent_name: str, text: str):
    """发送原始文本, 不附加 Enter。"""
    pane, session = await find_session(connection, agent_name)
    await session.async_send_text(text)


async def _is_gemini_in_shell_mode(session):
    """检测 Gemini 是否误入了 shell mode。"""
    try:
        content = await session.async_get_screen_contents()
        raw = "\n".join(
            content.line(j).string
            for j in range(content.number_of_lines)
        )
        screen = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?m').sub('', raw)
        return 'shell mode' in screen.lower() or '! ' in screen.split('\n')[-1]
    except Exception:
        return False


async def _send_to_gemini(session, message):
    """Gemini 专用发送：先 Escape 清状态 → 文本 → 延迟 → Enter → 检测 shell mode 自动恢复。"""
    # 先发 Escape 确保 Gemini 回到主输入框
    await session.async_send_text("\x1b")
    await asyncio.sleep(0.3)

    # 发送消息文本
    await session.async_send_text(message)
    await asyncio.sleep(0.5)

    # 发 Enter 提交
    await session.async_send_text("\r")
    await asyncio.sleep(1.0)

    # 检测是否误入 shell mode，如果是则退出
    if await _is_gemini_in_shell_mode(session):
        await session.async_send_text("exit\r")
        await asyncio.sleep(0.5)
        # 再试一次：Escape → 文本 → Enter
        await session.async_send_text("\x1b")
        await asyncio.sleep(0.3)
        await session.async_send_text(message)
        await asyncio.sleep(0.5)
        await session.async_send_text("\r")
        await asyncio.sleep(1.0)
        # 最终检查
        if await _is_gemini_in_shell_mode(session):
            print("  [gemini] WARNING: still in shell mode after retry")


async def cmd_say(connection, agent_name: str, message: str):
    """发送消息并提交。Gemini 使用专用发送逻辑避免进入 shell mode。"""
    resolved = resolve_agent(agent_name)
    pane, session = await find_session(connection, agent_name)

    if resolved == "gemini":
        await _send_to_gemini(session, message)
    else:
        await session.async_send_text(message)
        await asyncio.sleep(0.3)
        await session.async_send_text("\r")

    print(f"[sent to {agent_name}] {message[:80]}")


async def cmd_ask(connection, agent_name: str, question: str, wait_seconds: int = 15):
    """发送问题, 等待, 然后读取回复。"""
    resolved = resolve_agent(agent_name)
    pane, session = await find_session(connection, agent_name)

    if resolved == "gemini":
        started_at = time.time()
        await _send_to_gemini(session, question)
    else:
        started_at = None
        await session.async_send_text(question)
        await asyncio.sleep(0.3)
        await session.async_send_text("\r")

    print(f"[sent to {agent_name}] {question[:80]}")
    print(f"[waiting {wait_seconds}s...]")

    if resolved == "gemini":
        response = await _wait_for_gemini_response(started_at, wait_seconds)
        if response:
            print("--- response ---")
            print(response)
            return

    await asyncio.sleep(wait_seconds)

    content = await session.async_get_screen_contents()
    n = content.number_of_lines
    start = max(0, n - 35)
    lines = []
    for i in range(start, n):
        lines.append(content.line(i).string)
    print("--- response ---")
    print("\n".join(lines))


# ============================================================
# 入口
# ============================================================

HELP = __doc__


async def main():
    if len(sys.argv) < 2:
        print(HELP)
        return

    cmd = sys.argv[1].lower()
    conn = await iterm2.Connection().async_create()

    if cmd in ("list", "ls"):
        await cmd_list(conn)

    elif cmd == "read":
        if len(sys.argv) < 3:
            print("Usage: iterm_chat.py read <agent> [lines]")
            return
        agent = sys.argv[2]
        last_n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
        await cmd_read(conn, agent, last_n)

    elif cmd == "send":
        if len(sys.argv) < 4:
            print("Usage: iterm_chat.py send <agent> <text>")
            return
        await cmd_send(conn, sys.argv[2], sys.argv[3])

    elif cmd in ("say", "message", "msg"):
        if len(sys.argv) < 4:
            print("Usage: iterm_chat.py say <agent> <text>")
            return
        await cmd_say(conn, sys.argv[2], " ".join(sys.argv[3:]))

    elif cmd == "ask":
        if len(sys.argv) < 4:
            print("Usage: iterm_chat.py ask <agent> <question>")
            return
        await cmd_ask(conn, sys.argv[2], " ".join(sys.argv[3:]))

    else:
        print(f"Unknown command: {cmd}")
        print(HELP)


asyncio.run(main())
