"""Prompt templates for coding-agent adapters."""

from __future__ import annotations

from constrained_agent.agents.protocol import AgentContext

CODING_AGENT_SYSTEM_PROMPT = """You are the coding model inside constrained-agent-harness.

Return a single structured proposal that matches the required schema exactly.
Propose only bounded repository edits and sandbox commands.

Rules:
- Use only the repository context provided in this iteration.
- Do not rely on prior conversation history.
- Do not decide whether the overall task is complete; the controller decides that.
- Set completion_claimed to false in every response.
- Keep write_files aligned with the paths you edit.
- Use argument arrays for commands, never shell strings.
- Use risk_notes to capture concrete regression or uncertainty risks.
- If you propose a patch edit, unified_diff must be a full unified diff.
- If no edit or command is needed for a field, return an empty list.
"""


def render_coding_agent_prompt(
    context: AgentContext,
    *,
    validation_feedback: str | None = None,
) -> str:
    """Render the per-iteration coding prompt."""
    sections = [
        f"Goal summary:\n{context.goal_summary}",
        f"Repository map:\n{context.repository_map}",
        f"Candidate diff:\n{context.candidate_diff or '(none)'}",
        f"Evaluation failures:\n{context.evaluation_failures or '(none)'}",
        f"Prior rejected proposal feedback:\n{context.prior_rejected or '(none)'}",
        f"Remaining budget:\n{context.remaining_budget}",
        "Permitted actions:\n"
        + ("\n".join(f"- {action}" for action in context.permitted_actions) or "- none"),
        f"Protected path summary:\n{context.protected_summary}",
        f"Iteration:\n{context.iteration}",
        (
            "Response requirements:\n"
            "- Populate summary, hypothesis, evidence_considered, "
            "expected_effect, and risk_notes.\n"
            "- Populate edits and commands only when necessary.\n"
            "- completion_claimed must be false.\n"
            "- If you edit files, include those paths in write_files.\n"
            "- Leave diff as an empty string unless you have a precise proposal diff payload."
        ),
    ]
    if validation_feedback:
        sections.append(f"Validation feedback from the previous response:\n{validation_feedback}")
    return "\n\n".join(sections)
