# Architecture

The Constrained Agent Harness is built as a **constrained transition process**
over repository states. The controller owns all decisions; the model proposes
changes.

## System Overview

```
┌──────────────────────────────────────────────────────────┐
│                        Controller                         │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  State    │  │  Transition  │  │  Decision        │   │
│  │  Machine  │  │  Policy      │  │  Engine          │   │
│  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘   │
│       │               │                    │             │
└───────┼───────────────┼────────────────────┼─────────────┘
        │               │                    │
        ▼               ▼                    ▼
┌───────────────┐ ┌────────────┐ ┌────────────────────┐
│  Agent        │ │  Policy    │ │  Evaluator         │
│  (proposes)   │ │  (checks)  │ │  Pipeline          │
├───────────────┤ ├────────────┤ ├────────────────────┤
│ ADK /         │ │ Path / Cmd │ │ Tiered execution:  │
│ Scripted /    │ │ Dep /      │ │ T1 → T2 → T3       │
│ Replay        │ │ Approval   │ │ with short-circuit │
└───────┬───────┘ └────────────┘ └────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                     Persistence Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Run     │  │  Event   │  │ Candidate│  │ Artifact│ │
│  │  Store   │  │  Store   │  │  Store   │  │  Store  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLite (via SQLAlchemy)             │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### Controller

The controller orchestrates the run loop: for each iteration, it asks the
agent for a proposal, validates it against policy, evaluates the result with
the evaluator pipeline, and decides the next state transition. The controller
never delegates its decision authority to the model.

### State Machine

The state machine governs run lifecycle with seven decisions:

| Decision | Meaning |
|----------|---------|
| ACCEPT | Proposal accepted, new candidate created |
| REJECT | Proposal rejected, same state continues |
| ROLLBACK | Revert to a previous checkpoint |
| RETRY | Re-run the same iteration |
| BRANCH | Fork from a previous candidate |
| REQUEST_APPROVAL | Defer to human-in-the-loop |
| COMPLETE | Run finished successfully |
| FAIL | Run terminated with failure |

### Agent Protocol

Agents implement the `CodingAgent` protocol with a single method:
`propose_action(context) → AgentProposal`. Three implementations exist:

- **GoogleAdkCodingAgent** — wraps Google ADK for live model integration
- **ScriptedAgent** — applies predefined edits for reproducible testing
- **ReplayAgent** — replays recorded proposals for deterministic debugging

### Policy Engine

Stateless policy functions that validate agent proposals before execution:

- **PathPolicy** — checks writable/protected path patterns
- **CommandPolicy** — validates command arguments against allowed lists
- **DependencyPolicy** — enforces frozen dependency constraints
- **ApprovalPolicy** — checks required approval gates

### Evaluator Pipeline

Tiered evaluation with short-circuit semantics:

- **Tier 1**: Fast static checks (diff size, file count)
- **Tier 2**: Targeted tests (visible benchmark tests)
- **Tier 3**: Full test suites (slower, more comprehensive)

If any tier fails, the pipeline short-circuits and the controller decides
based on the partial evaluation vector.

### Context Builder

Fresh-session context reconstruction per iteration — no conversation history
leaks. The builder assembles:

- Goal contract
- Current workspace state (repository map, file tree)
- Git diff from checkpoint
- Evaluation failures and rejected-strategy evidence
- Remaining token budget

## Data Flow

1. **Initialize**: Load goal contract, set up sandbox, check point initial state
2. **Context**: Build fresh context from current state
3. **Propose**: Agent proposes changes (edits, commands, or declares completion)
4. **Validate**: Policy engine checks proposal against constraints
5. **Execute**: Apply edits, run commands in sandbox
6. **Evaluate**: Run evaluator pipeline
7. **Decide**: Controller determines next state transition
8. **Persist**: Store events, candidates, evaluations, artifacts
9. **Repeat**: Until COMPLETE, FAIL, or budget exhausted

## Persistence

The event store uses a **hash chain**: each event references the hash of the
previous event, providing tamper-evident audit trails. The artifact store uses
SHA-256 hashing with append-only semantics.

SQLite is the default backend (via SQLAlchemy + Alembic migrations), but the
storage interface supports alternative backends.
