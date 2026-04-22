# CCG — Claude · Codex · Gemini Driven

Multi-agent AI development team orchestrated in iTerm2. Three LLM-powered agents collaborate in a single terminal window, each with a distinct role, communicating through a shared chat bridge.

## Agents

| Agent | Model | Role |
|-------|-------|------|
| **Claude Code** | GLM-5.1 | Architect / Orchestrator |
| **Codex** | GPT-5.4 | Backend Engineer |
| **Gemini CLI** | Gemini 3 | Frontend Developer |

## Quick Start

```bash
# Prerequisites
pip3 install iterm2

# Launch the 3-pane team window (in the current directory)
./start

# Or specify a project directory
./start /path/to/your/project
```

This opens an iTerm2 window with three vertical panes — Claude, Codex, and Gemini — each running in the target project directory.

## Communication

Agents talk to each other via `iterm_chat.py`:

```bash
# List all panes
python3 iterm_chat.py list

# Send a message
python3 iterm_chat.py say codex "check main.py for bugs"

# Read an agent's screen
python3 iterm_chat.py read gemini 25

# Ask a question and wait for a reply
python3 iterm_chat.py ask claude "what's the API contract?"
```

## Workflow

```
Requirement → Claude (plan) → Codex (backend) → Contract frozen → Gemini (frontend) → Integration
```

1. **Claude** receives requirements, designs architecture, breaks down tasks
2. **Codex** implements backend logic and API endpoints
3. **Claude** freezes the API contract
4. **Gemini** builds the frontend against the frozen contract
5. **Claude** reviews and integrates

For full details, see [AGENTS.md](AGENTS.md).

## Project Structure

```
├── start              # One-command launcher (AppleScript + iTerm2 API)
├── iterm_chat.py      # Inter-agent communication bridge
├── AGENTS.md          # Collaboration protocol and role definitions
└── CLAUDE.md          # Claude Code session instructions
```

## Requirements

- **macOS with iTerm2 installed** (required — the entire communication layer depends on iTerm2's Python API)
- **iTerm2 Python API must be enabled**:
  1. Open iTerm2 → Settings (⌘,)
  2. Go to **General → Magic**
  3. Check **Python API**
  4. Switch the Python API setting to **Allow All**
- Claude Code, Codex CLI, Gemini CLI installed
- Python 3 with `iterm2` package (`pip3 install iterm2`)

## License

MIT
