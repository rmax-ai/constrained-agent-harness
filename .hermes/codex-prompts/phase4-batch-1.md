# Phase 4 — Batch 1: Google ADK Adapter + Structured Output

## Task

Implement the Google ADK adapter that integrates Gemini 3.5 Flash as the coding agent. Create credential validation, structured agent proposal, and response retry with validation feedback.

## Files to Create / Modify

### 1. `src/constrained_agent/agents/google_adk.py`

- `GoogleAdkCodingAgent` — implements the CodingAgent Protocol using Google ADK 2.x

**Key behavior:**
- `__init__`: takes model name, temperature, api_key or vertex config
- Validates credentials at construction time (not lazily)
- `async propose_action(context: AgentContext) -> AgentProposal`:
  1. Constructs a prompt from AgentContext fields
  2. Calls Gemini via ADK with structured output (JSON schema matching AgentProposal)
  3. Validates the response against expected schema
  4. On validation failure: retry with validation feedback in the prompt (up to 3 retries)
  5. Returns AgentProposal with all fields populated

**Model resolution precedence:** CLI > goal contract > env > default

**Credential validation:**
- Supports two auth modes:
  1. Google AI API key (CAH_GOOGLE_API_KEY env var)
  2. Vertex AI project/location (CAH_GOOGLE_CLOUD_PROJECT + CAH_GOOGLE_CLOUD_LOCATION + CAH_USE_VERTEX_AI)
- Validates at startup: `validate_credentials()` -> raises ModelUnavailableError if model can't be reached
- Reports resolved model via `get_model_info() -> dict`

**Structured output handling:**
- Use ADK's structured output to get typed response matching AgentProposal
- Map ADK response to AgentProposal fields (edits, commands, risk_notes, completion_claimed, etc.)
- Handle partial or malformed responses with retry

### 2. Update `src/constrained_agent/agents/protocol.py`

- Review existing AgentProposal, FileEdit, CommandRequest to ensure they match the spec requirements from section 5.3
- Add any missing fields (risk_notes, completion_claimed, evidence_considered, etc.)

### 3. `src/constrained_agent/agents/prompts.py`

- System prompt template for the coding agent
- Includes: goal summary, constraints, permitted actions, protected path summary
- Context is injected per-iteration
- Model never claims completion — prompt must NOT ask model to decide completion

## Tests

Create `tests/unit/test_adk_adapter.py`:
- `test_credential_validation_success` (mock)
- `test_credential_validation_failure`
- `test_proposal_parsing`
- `test_retry_on_validation_failure`

Mark live model tests with `@pytest.mark.live_model`.

## Files to Modify

- `src/constrained_agent/agents/__init__.py` — ensure GoogleAdkCodingAgent is exported
