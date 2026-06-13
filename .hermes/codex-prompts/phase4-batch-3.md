# Phase 4 — Batch 3: ADK Workflow Nodes + Integration

## Task

Create ADK workflow nodes and integrate the full ADK workflow into the controller. Add the live model smoke test.

## Files to Create

### 1. `src/constrained_agent/agents/adk_nodes.py`

ADK workflow nodes that compose the coding agent workflow:

- `PrepareContextNode` — prepares AgentContext for the next iteration
  - Uses ContextBuilder to build fresh context
  - Output: AgentContext

- `InvokeCodingAgentNode` — calls the coding agent
  - Uses GoogleAdkCodingAgent to get a proposal
  - Output: AgentProposal
  
- `ValidateProposalNode` — validates the proposal
  - Checks paths are writable
  - Checks commands are allowed
  - Returns validated (or rejected) proposal

- `CreateADKWorkflow` — composes the nodes into an ADK workflow:
  ```python
  def create_coding_agent_workflow() -> adk.Workflow:
      workflow = adk.Workflow("coding-agent")
      workflow.add_node("prepare_context", PrepareContextNode())
      workflow.add_node("invoke_agent", InvokeCodingAgentNode())
      workflow.add_node("validate", ValidateProposalNode())
      workflow.add_edge("prepare_context", "invoke_agent")
      workflow.add_edge("invoke_agent", "validate")
      return workflow
  ```

### 2. Update `src/constrained_agent/controller/controller.py`

- Add support for using the ADK agent:
  - When agent type is "google-adk", use GoogleAdkCodingAgent
  - When agent type is "scripted", use ScriptedAgent
  - The controller should work the same regardless of agent type

### 3. Live Model Smoke Test

Create `tests/integration/test_live_model.py` (marked `@pytest.mark.live_model`):
- Requires CAH_GOOGLE_API_KEY environment variable
- Tests:
  - `test_credential_validation` — valid credentials don't raise
  - `test_model_accessibility` — model is reachable
  - `test_structured_output` — model returns valid AgentProposal
  - `test_retry_on_invalid` — invalid response triggers retry
- Skip if no credentials available

## Files to Modify

- `src/constrained_agent/controller/controller.py` — agent selection
- `src/constrained_agent/cli/app.py` — wire up google-adk agent option
