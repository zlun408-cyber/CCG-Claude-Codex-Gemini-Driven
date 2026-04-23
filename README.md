# CCG — Claude · Codex · Gemini Driven

Multi-agent AI development team orchestrated in iTerm2. Three LLM-powered agents collaborate in a single terminal window, each with a distinct role, communicating through a shared chat bridge.

## Agents

| Agent | Model | Role |
|-------|-------|------|
| **Claude Code** | GLM-5.1 | Architect / Orchestrator |
| **Codex** | GPT-5.4 | Backend Engineer |
| **Gemini CLI** | Gemini 3 | Frontend Developer |

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
    └── iterm_chat.py
```

Copy commands:

```bash
cp -r .ccg /path/to/your-project/
cp start /path/to/your-project/

# Optional but recommended:
cp -r .claude /path/to/your-project/
```

Do **not** copy only `start` by itself. `start` depends on `.ccg/AGENTS.md` and `.ccg/iterm_chat.py`; cross-pane communication will not work without the `.ccg/` folder.

After copying, launch CCG from inside the target project root:

```bash
cd /path/to/your-project
./start
```

This opens an iTerm2 window with three vertical panes — Claude, Codex, and Gemini — each running in your project directory.

If your project does not have `CLAUDE.md`, `start` will auto-create one with instructions to read `.ccg/AGENTS.md` and use `.ccg/iterm_chat.py` for Codex/Gemini communication.

### Communication

Agents talk to each other via `.ccg/iterm_chat.py`:

```bash
# List all panes
python3 .ccg/iterm_chat.py list

# Send a message
python3 .ccg/iterm_chat.py say codex "check main.py for bugs"

# Read an agent's screen
python3 .ccg/iterm_chat.py read gemini 25

# Ask a question and wait for a reply
python3 .ccg/iterm_chat.py ask claude "what's the API contract?"
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

For full details, see [.ccg/AGENTS.md](.ccg/AGENTS.md).

## Project Structure

```
├── start                  # One-command launcher
├── CLAUDE.md              # Claude Code session instructions (auto-generated)
└── .ccg/
    ├── iterm_chat.py      # Inter-agent communication bridge
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
