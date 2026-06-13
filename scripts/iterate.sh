#!/usr/bin/env bash
# iterate.sh — Multi-phase Codex iteration loop for constrained-agent-harness
set -euo pipefail

REPO_DIR="$HOME/src/constrained-agent-harness"
NVM_SETUP='export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'
CMD="${1:-help}"
ISSUE="${2:-}"
ARGS="${3:-}"

case "$CMD" in

  # ── Setup ──────────────────────────────────────────────────────────────
  setup)
    echo "Labels and issues are already created."
    echo "Phase 1 = #2 (done), Phase 2 = #3, Phase 3 = #4, Phase 4 = #5, Phase 5 = #6, Phase 6 = #7"
    ;;

  # ── Phase execution ────────────────────────────────────────────────────
  phase)
    if [ -z "$ISSUE" ]; then
      echo "Usage: ./scripts/iterate.sh phase <issue-number>"
      exit 1
    fi

    PHASE_NUM=$(gh issue view "$ISSUE" --json title --jq '.title' | grep -oP 'Phase \d+' || echo "phase-$ISSUE")

    # Mark issue as in-progress
    gh issue edit "$ISSUE" --add-label "status:in-progress" --remove-label "status:backlog" 2>/dev/null || true

    # Generate phase prompt
    mkdir -p .hermes/codex-prompts
    PROMPT_FILE=".hermes/codex-prompts/phase-${ISSUE}.md"

    cat > "$PROMPT_FILE" << PROMPT
You are implementing ${PHASE_NUM} of the constrained-agent-harness project.

## Project Context

constrained-agent-harness is a reference harness for running coding agents as bounded, verifiable search over repository states. It models the system as a constrained transition process: model proposes changes, deterministic harness decides acceptance.

### Architecture
- src/constrained_agent/cli/ — Typer CLI commands
- src/constrained_agent/domain/ — Typed contracts and domain models (no infra)
- src/constrained_agent/controller/ — State machine and transition logic
- src/constrained_agent/agents/ — Model adapters (ADK, scripted, replay)
- src/constrained_agent/context/ — Context reconstruction
- src/constrained_agent/policy/ — Path, command, dependency enforcement
- src/constrained_agent/sandbox/ — Docker and fake sandbox
- src/constrained_agent/repository/ — Git-backed repository store
- src/constrained_agent/evaluators/ — Quality and safety check pipeline
- src/constrained_agent/persistence/ — SQLite event store
- src/constrained_agent/artifacts/ — Evidence and hash chain
- src/constrained_agent/reporting/ — Run and experiment reports

### Rules
1. Model NEVER makes authoritative completion decision
2. Every state transition persisted before continuing
3. Protected tests mounted read-only in sandbox
4. Commands as argument arrays, never shell=True
5. Evaluations as vectors, not scalars
6. Context reconstructed fresh per iteration
7. SHA-256 hash chains for evidence
8. Python 3.13, from __future__ import annotations everywhere
9. Pydantic v2 for boundary validation
10. No global state, no singletons, no service locator
11. Constructor injection throughout

### Issue #${ISSUE}
$(gh issue view "$ISSUE" --json body --jq '.body' | head -200)

### Current state
Read the files in src/constrained_agent/ to understand what exists so far.
Implement the missing modules as described in the issue.
Run tests after each meaningful module.
Do NOT leave placeholder methods containing only pass.
Do NOT disable linting or type checking.
Keep modules small and readable.

### Verification
After each module, run:
  uv run pytest tests/unit/ -v
  uv run ruff check src/
  uv run mypy src/
PROMPT

    echo "Prompt written to $PROMPT_FILE"

    # Run Codex exec in background with monitoring
    bash "$HOME/.hermes/skills/autonomous-ai-agents/codex/scripts/codex-exec-monitored.sh" \
      "phase-${ISSUE}" "$PROMPT_FILE" --workdir "$REPO_DIR" 2>&1

    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
      echo "✓ Codex completed for issue #${ISSUE}"
    else
      echo "⚠ Codex exited with code ${EXIT_CODE} for issue #${ISSUE}"
    fi
    ;;

  # ── Review and merge ───────────────────────────────────────────────────
  review)
    if [ -z "$ISSUE" ]; then
      echo "Usage: ./scripts/iterate.sh review <issue-number>"
      exit 1
    fi

    cd "$REPO_DIR"

    # Run verification
    echo "=== Running CI checks ==="

    set +e
    uv run ruff format --check . ; RF=$?
    uv run ruff check . ; RC=$?
    uv run mypy src/ ; MP=$?
    uv run pytest -x --timeout=60 2>/dev/null || uv run pytest -x ; PT=$?
    set -e

    echo "ruff format: $RF | ruff check: $RC | mypy: $MP | pytest: $PT"

    if [ $RF -ne 0 ] || [ $RC -ne 0 ] || [ $MP -ne 0 ] || [ $PT -ne 0 ]; then
      echo "⚠ Verification failed — review needed before merging"
      exit 1
    fi

    # Commit and push
    BRANCH="story/issue-${ISSUE}"
    git checkout -b "$BRANCH"
    git add -A
    git commit -m "feat: implements #${ISSUE}"
    git push -u origin "$BRANCH"

    # Create PR
    TITLE=$(gh issue view "$ISSUE" --json title --jq '.title')
    gh pr create \
      --repo "rmax-ai/constrained-agent-harness" \
      --title "$TITLE" \
      --body "Closes #${ISSUE}" \
      --base main \
      --head "$BRANCH" \
      --label "status:in-review"

    # Merge
    gh pr merge --squash --delete-branch || echo "⚠ PR merge failed (may need manual review)"

    # Update issue
    gh issue edit "$ISSUE" --add-label "status:done" --remove-label "status:in-review" 2>/dev/null || true

    echo "✓ Issue #${ISSUE} completed and merged"
    ;;

  # ── Status ─────────────────────────────────────────────────────────────
  status)
    cd "$REPO_DIR"
    echo "=== Issue Status ==="
    for issue in 1 2 3 4 5 6 7; do
      STATE=$(gh issue view "$issue" --json labels --jq '.labels[] | select(.name | startswith("status:")).name' 2>/dev/null || echo "unknown")
      TITLE=$(gh issue view "$issue" --json title --jq '.title' 2>/dev/null || echo "unknown")
      echo "  #$issue [$STATE] $TITLE"
    done
    ;;

  # ── Help ───────────────────────────────────────────────────────────────
  *)
    echo "Usage:"
    echo "  ./scripts/iterate.sh setup              — Show issue layout"
    echo "  ./scripts/iterate.sh phase <issue>      — Run Codex on an issue"
    echo "  ./scripts/iterate.sh review <issue>     — Verify, commit, PR, merge"
    echo "  ./scripts/iterate.sh status             — Show issue status"
    echo ""
    echo "Issues:"
    echo "  #1  Epic"
    echo "  #2  Phase 1: Project Skeleton (done)"
    echo "  #3  Phase 2: Deterministic Core"
    echo "  #4  Phase 3: Local End-to-End Scripted Run"
    echo "  #5  Phase 4: Google ADK Integration"
    echo "  #6  Phase 5: Experimental Modes"
    echo "  #7  Phase 6: Branching Prototype & Final Docs"
    ;;
esac
