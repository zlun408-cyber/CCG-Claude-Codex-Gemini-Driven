#!/usr/bin/env python3
"""
iTerm2 Multi-Agent Chat Bridge
===============================
放到任意项目目录下即可使用。通过 iTerm2 Python API 实现
Claude Code / Codex / Gemini 三个 pane 之间的双向通信。

依赖: pip3 install iterm2

用法:
  python3 iterm_chat.py list                      列出所有 pane
  python3 iterm_chat.py read <agent> [N]          读取 agent 屏幕最近 N 行 (默认 40)
  python3 iterm_chat.py send <agent> <text>       发送原始文本 (无 Enter)
  python3 iterm_chat.py say <agent> <text>        发送消息并提交 (自动 Enter)
  python3 iterm_chat.py ask <agent> <question>    发送问题, 等待回复, 打印结果

  <agent> 可以是: claude / codex / gemini / 1 / 2 / 3

示例:
  python3 iterm_chat.py say codex "帮我检查 main.py 有没有 bug"
  python3 iterm_chat.py ask gemini "解释一下这个正则: ^(?=.*[A-Z]).{8,}$"
  python3 iterm_chat.py read codex
  python3 iterm_chat.py read gemini 25

注意:
  - Gemini 的 TUI 会吞掉紧跟文本发送的 Enter, 所以文本和 Enter 之间有 0.3s 延迟
  - 读取只能看到当前屏幕缓冲区, 滚出屏幕的内容无法获取
  - 如果 Gemini 进入了 shell mode, 先发送 Escape 退出: ./iterm_chat.py send gemini $'\\x1b'
"""

import asyncio
import iterm2
import os
import sys
from pathlib import Path

# ============================================================
# Agent 识别: 关键词 -> pane 匹配规则
# ============================================================
AGENT_KEYWORDS = {
    "claude": ["claude"],
    "codex":  ["codex"],
    "gemini": ["gemini"],
}

AGENT_ALIASES = {
    "1": "claude", "2": "codex", "3": "gemini",
    "c": "claude", "cx": "codex", "g": "gemini",
}


def resolve_agent(name: str) -> str:
    """将用户输入的 agent 名解析为标准名 (claude/codex/gemini)。"""
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
    """对一组 sessions 按名称分类，返回 {agent_name: (pane_index, session)}。

    先按名称关键词匹配，未匹配的 pane 按位置兜底：
    Pane 1 = claude, Pane 2 = codex, Pane 3 = gemini
    """
    agents = {}
    for i, s in enumerate(sessions):
        pane = i + 1
        name_lower = s.name.lower()
        for agent_name, keywords in AGENT_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                agents[agent_name] = (pane, s)
                break
    # 位置兜底
    if len(sessions) >= 3 and len(agents) < 3:
        position_map = {0: "claude", 1: "codex", 2: "gemini"}
        for idx, agent_name in position_map.items():
            if agent_name not in agents:
                agents[agent_name] = (idx + 1, sessions[idx])
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


async def _find_team_window(connection, target_agent=None):
    """扫描所有 iTerm2 窗口，找到包含 Claude+Codex+Gemini 的团队窗口。

    策略 (按优先级):
    0. 最高优先：通过 .ccg/.sessions 保存的精确 session ID 匹配
    1. 次优先：包含自身 session 的窗口（自己所在的窗口就是团队窗口）
    2. 标准团队窗口：3 pane 且 3 个名字都匹配
    3. 有目标 agent 的窗口 +20 分
    4. 位置兜底保证 3 pane 总能匹配满
    """
    app = await iterm2.async_get_app(connection)

    # 策略 0: 通过保存的 session ID 精准匹配
    saved = _load_saved_sessions()
    if saved:
        for window in app.windows:
            for tab in window.tabs:
                agents = {}
                for i, s in enumerate(tab.sessions):
                    for agent_name, sid in saved.items():
                        if sid in s.session_id or s.session_id.endswith(sid):
                            agents[agent_name] = (i + 1, s)
                            break
                if len(agents) == len(saved):
                    return tab, agents

    # 策略 1+: 原有的名称 + 位置匹配逻辑
    own_sid = _get_own_session_id()

    best = None          # (score, tab, agents_dict)

    for window in app.windows:
        for tab in window.tabs:
            sessions = tab.sessions
            agents = _classify_sessions(sessions)

            # 基础分
            if len(sessions) == 3 and len(agents) == 3:
                score = 100
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
    import re
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
        await _send_to_gemini(session, question)
    else:
        await session.async_send_text(question)
        await asyncio.sleep(0.3)
        await session.async_send_text("\r")

    print(f"[sent to {agent_name}] {question[:80]}")
    print(f"[waiting {wait_seconds}s...]")
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
