# AGENTS.md — Multi-Agent Collaboration Protocol

> This file defines the collaboration protocol for the 3-role, 4-pane iTerm2 development team.
> Lives in .ccg/AGENTS.md. All agents should read it on session start (via CLAUDE.md).

## Team Structure

### Core Roles (fixed)

| Agent | Model | Pane | Role |
|-------|-------|------|------|
| **Claude Code** | GLM-5.1 | 1 | User Proxy / Architect / Orchestrator |
| **Codex** | GPT-5.4 | 2 | Engineer (backend, logic, test code) |
| **Gemini CLI** | Gemini 3 | 3 | Frontend Developer (UI/UX) |

### Verification Pane (optional but recommended)

| Agent | Model | Pane | Role |
|-------|-------|------|------|
| **Codex2** | GPT-5.4 | 4 | Verification Worker (testing, regression, build checks) |

> The team always has **3 core roles**: Claude, Codex, Gemini.
> A **4th pane** may be enabled for verification work. The default verifier is **Codex2**.
> Codex2 is an execution support worker, not a new decision-making role.

## Authority Model

### Claude is the sole proxy for the user
- Claude fully represents the user in team coordination.
- Only Claude may approve plans, scope changes, tradeoffs, priorities, and final decisions on the user's behalf.
- Codex, Gemini, and Codex2 must not interpret user intent independently when a decision is needed.
- If anything is ambiguous, escalate to Claude first; Claude escalates to the user when needed.

## Role Definitions

### Claude — User Proxy, Architect & Orchestrator
- Receive project requirements, break down into tasks
- Represent the user in all internal coordination
- Design system architecture, define module boundaries
- Freeze API contracts (field names, error states, pagination rules) before parallel work begins
- Assign work to Codex, Gemini, and Codex2 when needed
- Collect progress, blockers, risks, and completion reports from all other agents
- Review, integrate, and report consolidated status back to the user

### Codex — Engineer
- Implement core business logic, API endpoints, database operations
- Fix bugs, write tests, refactor code
- Handle CI/build failures, regression fixes
- Prefer small verified steps: reproduce → minimal fix → test
- Report implementation status, blockers, and completion back to Claude

### Gemini — Frontend Developer
- Build UI with focus on aesthetics and interaction quality
- React (TypeScript) / Angular preferred
- Vanilla CSS for fine-grained visual control (unless Tailwind etc. is specified)
- Responsive layout, dark mode, animations, accessibility
- Report implementation status, blockers, UX concerns, and completion back to Claude

### Codex2 — Verification Worker
- Run tests, smoke checks, regression checks, and build verification
- Reproduce bugs and validate whether fixes actually resolve them
- Verify integration quality without taking over product or architecture decisions
- Report findings, failures, risks, and pass/fail summaries back to Claude
- Keep Claude's main pane clean by offloading noisy verification work

## Workflow

```
1. Requirement received
   └→ Claude: analyze → task breakdown → architecture plan → get user approval

2. Backend first
   └→ Codex: implement core logic, API layer, test stubs → report to Claude

3. Freeze contract
   └→ Claude: lock down API spec, field names, error handling, loading states

4. Frontend parallel
   └→ Gemini: build UI against frozen contract → report to Claude

5. Verification
   └→ Codex2: run tests / regression / build checks → report to Claude

6. Integration
   └→ Claude: review all changes, coordinate fixes, final verification, report to user
```

## Communication (.ccg/iterm_chat.py)

```bash
# Send message
python3 .ccg/iterm_chat.py say codex "message"
python3 .ccg/iterm_chat.py say gemini "message"
python3 .ccg/iterm_chat.py say codex2 "message"

# Read screen
python3 .ccg/iterm_chat.py read codex [N]       # last N lines
python3 .ccg/iterm_chat.py read gemini [N]
python3 .ccg/iterm_chat.py read codex2 [N]
```

## Reporting Rules

- Claude is the **only** agent that reports status outward to the user.
- Codex, Gemini, and Codex2 must report all of the following back to Claude:
  - task start
  - progress updates
  - blockers
  - risks
  - completion / handoff summary
- Agents may communicate directly for execution details, but they must not bypass Claude for approval, reprioritization, or final status.

## Task Format

When Claude assigns tasks to Codex, Gemini, or Codex2, include:
- **Goal**: what to achieve
- **Files**: which files are involved
- **Constraints**: what must not change, performance requirements, etc.
- **Acceptance criteria**: how to verify it's done
- **Reporting expectation**: what must be reported back to Claude

## Boundaries — What Each Role Must NOT Do

### Claude (User Proxy / Architect)
- **Do NOT** directly implement features or write production code — delegate to Codex or Gemini
- **Do NOT** override Gemini's UI/visual decisions without a user-level reason
- **Do NOT** skip user approval on architecture plans before execution begins
- **Do NOT** hand off final user communication to another agent

### Codex (Engineer)
- **Do NOT** modify frontend UI files (components, styles, layouts) — that is Gemini's domain
- **Do NOT** change API contracts unilaterally — propose changes to Claude, who updates the frozen spec
- **Do NOT** start implementation before architecture plan is approved and contract is defined
- **Do NOT** treat your own interpretation as user intent — Claude represents the user
- **Minimal exception**: may touch frontend files only for integration wiring (e.g. fixing an import path), never for visual or UX decisions

### Gemini (Frontend)
- **Do NOT** touch database schema, server-side business logic, or backend config
- **Do NOT** modify API endpoint implementations — consume interfaces as-is from the frozen contract
- **Do NOT** start building pages before the API contract is frozen
- **Do NOT** add backend logic inside frontend code (no client-side workarounds for missing APIs — escalate to Claude)
- **Do NOT** treat UX preference changes as approved unless Claude confirms them

### Codex2 (Verification)
- **Do NOT** make product, UX, architecture, or scope decisions
- **Do NOT** silently fix production code unless Claude explicitly assigns implementation work
- **Do NOT** replace Codex as the implementation owner
- **Do NOT** report final conclusions to the user directly — report to Claude

## File Ownership

| Directory / File Pattern | Owner | Others |
|---|---|---|
| `src/api/`, `src/services/`, `src/models/`, `src/db/` | **Codex** | Read-only |
| `src/components/`, `src/pages/`, `src/styles/`, `*.css`, `*.tsx` (UI) | **Gemini** | Read-only |
| `*.spec.*`, `*.test.*`, `__tests__/` | **Codex** | Read-only |
| Verification scripts, test outputs, regression logs | **Codex2** | Read-only |
| `docs/api/`, contract files, architecture docs | **Claude** | Read-only |
| Config files (`tsconfig`, `package.json`, etc.) | **Codex** (propose) → **Claude** (approve) | — |

> "Read-only" means you may read for context, but must NOT edit. If a change is needed, request the owner to make it.

## Handoff Protocol

### Codex → Claude
Codex must deliver:
- Implementation summary
- Files changed
- API endpoint definitions with HTTP method, path, request/response schema
- TypeScript interface files (or equivalent type definitions)
- Error codes and states: what errors can occur, status codes, error response shape
- Mock data or running dev server details when needed
- Edge case notes: empty state, loading state, permission denied, pagination rules
- Known risks / follow-ups

### Claude → Gemini
Claude hands Gemini the frozen contract and implementation-ready context:
- Approved API contract
- Field names and response shapes
- Error handling rules
- Loading / empty / permission / pagination states
- Any constraints from the user or backend

### Gemini → Claude
Gemini must deliver:
- UI implementation summary
- Files changed
- Any UX-driven change requests
- Integration issues found
- Known risks / follow-ups

### Gemini → Codex (via Claude)
Gemini must submit a **change request** to Claude (not directly to Codex):
- What is needed and why (UX justification)
- Proposed interface change
- Impact assessment

Claude evaluates, updates the frozen contract if approved, then assigns Codex.

### Codex2 → Claude
Codex2 must deliver:
- Commands run
- What was verified
- Pass/fail result
- Reproduction notes for failures
- Regression or build risks
- Recommended next action

## Conflict Resolution

1. **Interface disagreement between Codex and Gemini**
   - Both state their case: Codex from engineering complexity, Gemini from UX impact
   - **Claude decides** as the user proxy and architect, updates the frozen contract
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
| Contract frozen | **Claude** | API spec is locked, Codex & Gemini acknowledge |
| Backend verified | **Codex** | Logic implemented and self-checked before handoff |
| Frontend verified | **Gemini** | Pages render correctly against real/mock API |
| Verification complete | **Codex2** | Tests/build/regression checks executed and reported |
| Integration review | **Claude** | Consolidated end-to-end check before delivery to user |

## Escalation to User

Escalate to the user (do not decide among yourselves) when:
- Requirements are ambiguous or contradictory
- A technology choice affects the user's existing infrastructure
- A tradeoff has significant cost/performance/time implications
- Scope change is needed (adding/removing features)
- Claude determines that user intent cannot be safely inferred

## Conventions

- Small commits, verify each step
- Backend closes first, then frontend integrates
- API contract is frozen before Gemini starts UI work
- Verification work should be offloaded to Codex2 when the 4th pane is available
- All agents work in the same project directory
- When in doubt, ask Claude; Claude when in doubt, ask the user
