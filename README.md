# CCG — Claude · Codex · Gemini Driven

Multi-agent AI development team orchestrated in iTerm2. Three core LLM roles collaborate in a single terminal window, with an optional fourth verification pane for testing and regression work.

## Team Structure

### Core roles

| Agent | Model | Role |
|-------|-------|------|
| **Claude Code** | GLM-5.1 | User Proxy / Architect / Orchestrator |
| **Codex** | GPT-5.4 | Engineer |
| **Gemini CLI** | Gemini 3 | Frontend Developer |

### Optional verification pane

| Agent | Model | Role |
|-------|-------|------|
| **Codex2** | GPT-5.4 | Verification Worker |

The team model is **3 roles + 4 panes**:
- 3 fixed core roles: Claude, Codex, Gemini
- 1 recommended verification pane: Codex2

Claude is the only agent that represents the user. Codex, Gemini, and Codex2 all report back to Claude.

## Usage

### Add to a project

To use CCG in another project, copy the required launcher files into that project's root.

Required:

- `start`
- the entire `.ccg/` directory

Generated automatically:

- `CLAUDE.md` — created by `./start` if it does not already exist

Optional but recommended:

- `.claude/` — copy this too if you want Claude Code to keep the same local permission/settings behavior as this template

The target project should look like this:

```text
/path/to/your-project/
├── start
├── CLAUDE.md              # auto-created if missing
├── .claude/               # optional, recommended for Claude Code settings
└── .ccg/
    ├── AGENTS.md
    ├── iterm_chat.py
    ├── launch_claude.sh
    ├── launch_codex.sh
    ├── launch_gemini.sh
    ├── launch_codex2.sh
    └── claude_gateway_proxy.py
```

Copy commands:

```bash
cp -r .ccg /path/to/your-project/
cp start /path/to/your-project/

# Optional but recommended:
cp -r .claude /path/to/your-project/
```

Do **not** copy only `start` by itself, or only pick a few files from `.ccg/`.
`start` depends on the whole `.ccg/` directory:

- `.ccg/AGENTS.md` defines the collaboration protocol.
- `.ccg/iterm_chat.py` handles cross-pane communication.
- `.ccg/launch_*.sh` starts each pane and stamps stable iTerm session IDs.
- `.ccg/claude_gateway_proxy.py` keeps the Claude pane compatible with tokenhubpro by stripping unsupported Claude Code request fields.

After copying, launch CCG from inside the target project root:

```bash
cd /path/to/your-project
./start
```

This opens an iTerm2 window with four panes by default — Claude, Codex, Gemini, and Codex2 — each running in your project directory.

If your project does not have `CLAUDE.md`, `start` will auto-create one with instructions to read `.ccg/AGENTS.md` and use `.ccg/iterm_chat.py` for Codex, Gemini, and Codex2 coordination.

### Communication

Agents talk to each other via `.ccg/iterm_chat.py`:

```bash
# List all panes
python3 .ccg/iterm_chat.py list

# Send a message
python3 .ccg/iterm_chat.py say codex "check main.py for bugs"
python3 .ccg/iterm_chat.py say codex2 "run regression checks"

# Read an agent's screen
python3 .ccg/iterm_chat.py read gemini 25
python3 .ccg/iterm_chat.py read codex2 25

# Ask a question and wait for a reply
python3 .ccg/iterm_chat.py ask claude "what's the frozen API contract?"
```

## Workflow

```text
Requirement → Claude (plan) → Codex (implementation) → Claude freezes contract → Gemini (frontend) → Codex2 (verification) → Claude (integration and user report)
```

1. **Claude** receives requirements, represents the user, designs architecture, and breaks down tasks
2. **Codex** implements backend logic, APIs, and test code, then reports back to Claude
3. **Claude** freezes the API contract
4. **Gemini** builds the frontend against the frozen contract, then reports back to Claude
5. **Codex2** runs verification, tests, regression checks, and build checks, then reports back to Claude
6. **Claude** reviews, integrates, and reports consolidated status to the user

For full details, see [.ccg/AGENTS.md](.ccg/AGENTS.md).

## Project Structure

```text
├── start                  # One-command launcher
├── CLAUDE.md              # Claude Code session instructions (auto-generated)
└── .ccg/
    ├── iterm_chat.py      # Inter-agent communication bridge
    ├── launch_*.sh        # Per-agent pane launchers
    ├── claude_gateway_proxy.py
    │                      # Claude Code/tokenhubpro compatibility proxy
    └── AGENTS.md          # Collaboration protocol and role definitions
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
