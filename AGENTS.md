# AGENTS.md — Multi-Agent Collaboration Protocol

> This file defines the collaboration protocol for the 3-agent iTerm2 development team.
> Copy this file into any new project root. All agents should read it on session start.

## Team Members

| Agent | Model | Pane | Role |
|-------|-------|------|------|
| **Claude Code** | GLM-5.1 | 1 | Architect / Orchestrator |
| **Codex** | GPT-5.4 | 2 | Engineer (backend, logic, tests) |
| **Gemini CLI** | Gemini 3 | 3 | Frontend Developer (UI/UX) |

## Role Definitions

### Claude — Architect & Orchestrator
- Receive project requirements, break down into tasks
- Design system architecture, define module boundaries
- Freeze API contracts (field names, error states, pagination rules) before parallel work begins
- Coordinate Codex and Gemini, merge results
- Review and integrate

### Codex — Engineer
- Implement core business logic, API endpoints, database operations
- Fix bugs, write tests, refactor code
- Handle CI/build failures, regression fixes
- Prefer small verified steps: reproduce → minimal fix → test

### Gemini — Frontend Developer
- Build UI with focus on aesthetics and interaction quality
- React (TypeScript) / Angular preferred
- Vanilla CSS for fine-grained visual control (unless Tailwind etc. is specified)
- Responsive layout, dark mode, animations, accessibility

## Workflow

```
1. Requirement received
   └→ Claude: analyze → task breakdown → architecture plan → get user approval

2. Backend first
   └→ Codex: implement core logic, API layer, test stubs → verify

3. Freeze contract
   └→ Claude: lock down API spec, field names, error handling, loading states

4. Frontend parallel
   └→ Gemini: build UI against frozen contract

5. Integration
   └→ Claude: review all changes, coordinate fixes, final verification
```

## Communication (iterm_chat.py)

```bash
# Send message
python3 iterm_chat.py say codex "message"
# Gemini needs direct iTerm2 API (keyword detection doesn't match pane 3)

# Read screen
python3 iterm_chat.py read codex [N]       # last N lines

# Gemini direct send (use when iterm_chat.py can't find gemini)
python3 -c "
import asyncio, iterm2
async def main():
    conn = await iterm2.Connection().async_create()
    app = await iterm2.async_get_app(conn)
    sessions = app.current_window.current_tab.sessions
    s = sessions[2]
    await s.async_send_text('YOUR MESSAGE')
    await asyncio.sleep(0.3)
    await s.async_send_text('\r')
asyncio.run(main())
"
```

## Task Format (for Codex)

When Claude assigns tasks to Codex, include:
- **Goal**: what to achieve
- **Files**: which files are involved
- **Constraints**: what must not change, performance requirements, etc.
- **Acceptance criteria**: how to verify it's done

## Boundaries — What Each Role Must NOT Do

### Claude (Architect)
- **Do NOT** directly implement features or write production code — delegate to Codex or Gemini
- **Do NOT** override Gemini's UI/visual decisions — defer to Gemini on aesthetics
- **Do NOT** skip user approval on architecture plans before execution begins

### Codex (Engineer)
- **Do NOT** modify frontend UI files (components, styles, layouts) — that is Gemini's domain
- **Do NOT** change API contracts unilaterally — propose changes to Claude, who updates the frozen spec
- **Do NOT** start implementation before architecture plan is approved and contract is defined
- **Minimal exception**: may touch frontend files only for integration wiring (e.g. fixing an import path), never for visual or UX decisions

### Gemini (Frontend)
- **Do NOT** touch database schema, server-side business logic, or backend config
- **Do NOT** modify API endpoint implementations — consume interfaces as-is from the frozen contract
- **Do NOT** start building pages before the API contract is frozen
- **Do NOT** add backend logic inside frontend code (no client-side workarounds for missing APIs — escalate to Claude)

## File Ownership

| Directory / File Pattern | Owner | Others |
|---|---|---|
| `src/api/`, `src/services/`, `src/models/`, `src/db/` | **Codex** | Read-only |
| `src/components/`, `src/pages/`, `src/styles/`, `*.css`, `*.tsx` (UI) | **Gemini** | Read-only |
| `*.spec.*`, `*.test.*`, `__tests__/` | **Codex** | Read-only |
| `docs/api/`, contract files, architecture docs | **Claude** | Read-only |
| Config files (`tsconfig`, `package.json`, etc.) | **Codex** (propose) → **Claude** (approve) | — |

> "Read-only" means you may read for context, but must NOT edit. If a change is needed, request the owner to make it.

## Handoff Protocol

### Codex → Gemini (backend to frontend)
Codex must deliver:
- **API endpoint definitions** with HTTP method, path, request/response schema
- **TypeScript interface files** (or equivalent type definitions)
- **Error codes and states**: what errors can occur, status codes, error response shape
- **Mock data or running dev server** for Gemini to develop against
- **Edge case docs**: empty state, loading state, permission denied, pagination rules

### Gemini → Codex (frontend requests backend changes)
Gemini must submit a **change request** to Claude (not directly to Codex):
- What is needed and why (UX justification)
- Proposed interface change
- Impact assessment

Claude evaluates, updates the frozen contract if approved, then assigns Codex.

## Conflict Resolution

1. **Interface disagreement between Codex and Gemini**
   - Both state their case: Codex from engineering complexity, Gemini from UX impact
   - **Claude decides** as the architect, updates the frozen contract
   - Both accept and implement the decision

2. **Unclear requirements**
   - The agent who discovers the ambiguity **stops and reports to Claude immediately**
   - Claude clarifies with the user, updates the plan
   - No agent implements assumptions

3. **Blocked by another agent's work**
   - Report to Claude with: what you need, from whom, why you're blocked
   - Claude re-prioritizes or re-assigns

4. **Scope creep (an agent doing work outside their role)**
   - Any agent who notices it flags it immediately
   - Claude corrects the assignment
   - The out-of-scope work is reverted or handed to the correct owner

## Quality Gates

| Gate | Owner | Checkpoint |
|------|-------|------------|
| Architecture approved | **Claude** | User confirms plan before any code is written |
| Contract frozen | **Claude** | API spec is locked, both Codex & Gemini acknowledge |
| Backend verified | **Codex** | Tests pass, endpoints return correct responses |
| Frontend verified | **Gemini** | Pages render correctly against real/mock API |
| Integration review | **Claude** | End-to-end check before delivery to user |

## Escalation to User

Escalate to the user (do not decide among yourselves) when:
- Requirements are ambiguous or contradictory
- A technology choice affects the user's existing infrastructure
- A tradeoff has significant cost/performance/time implications
- Scope change is needed (adding/removing features)

## Conventions

- Small commits, verify each step
- Backend closes first, then frontend integrates
- API contract is frozen before Gemini starts UI work
- All agents work in the same project directory
- When in doubt, ask Claude; Claude when in doubt, ask the user
