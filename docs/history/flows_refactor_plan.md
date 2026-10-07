> **HISTORICAL (replaced 2026-10-05).** The two flows below (`conversation-flow`, `motion-flow`), Brain asking them one after the other, the fast path and `robot_context` no longer exist: ai-agent now has four flows behind one router and Brain makes one call. Read `../guides/architecture.md` for the current design; this file only explains why the first split was made.

# Flows refactor plan (conversation-flow and motion-flow)

Status: **IMPLEMENTED 2026-09-30** (steps 1 to 7 below, nothing committed or pushed). See "As built" at the end for where it differs from this plan.
Snapshot taken before any change: `D:\Hobbys\IA\OBLIVION_snapshots\pre_motion_split_2026-09-30\`
(ai-agent, brain_microservice, contracts, deployment, plus each repo's `git status` and HEAD; venvs and `.env` excluded).

## Goal

Make ai-agent able to host several agents ("flows"). Two now, more later:

- `conversation-flow`: the current agent, without any robot logic.
- `motion-flow`: turns a request into an ordered list of arm movements.

They live in the same service, venv and deployment. Brain stays the only coordinator. The agents only decide, they never move hardware.

## Rules

- Top-level folders do not change (`application/`, `domain/`, `infrastructure/`, `prompts/`, `schema/`, `config/`, `tests/`, `docs/`, `mcps/`). Only subfolders are added where a flow needs them.
- Public names use hyphens (`conversation-flow`, `motion-flow`: routes, logs, config keys). Python packages use underscores.
- One engine, many flows. The engine stays common: `phase_runner`, `flow_state`, `metrics`, `failure`, `model_selection`, `clarification`, `answer_check`.
- **One phase per file.** Each phase file declares everything it uses as constants at the top (phase id, step name, prompt file, schema pieces, default model, format name, intent, model env var) so debugging shows what a phase uses.
- **Prompts are flat**: `prompts/<id>_<name>.txt`, no subfolders. The phase file says which prompt it uses.
- Repo rules still apply: `shared_logging` only, envelope responses, `contracts` first for wire changes, no commit or push unless asked.

## Problems today

| Problem | Where |
|---|---|
| `Pipeline` hardcodes triage, the fast path, the draft writer and `find_directive`. | `application/orchestration/pipeline.py` |
| Phases 4, 5, 6 live in `action_executor.py`, 9 in `answer_check.py`, 99 in `clarification.py`. Only 1, 2, 3, 7, 8 have their own file. | `application/orchestration/` |
| A phase's prompt, schema pieces and model key come from three central dicts. | `system_prompts/general.py`, `schemas.py`, `metrics.PHASE_NAMES` |
| Phase ids are global ints; they also key `step_models.json` and `AI_AGENT_MODEL_PHASE_<n>`. | `model_selection.py` |
| Robot logic sits in the conversation flow. | `robot_directive.py`, prompts, `directive` DTOs |

## Target shape (changed or new parts only)

```
application/orchestration/
  pipeline.py                  # generic: runs the steps of any Flow
  flow.py                      # NEW: Flow dataclass + FlowRegistry
  phases/
    common/
      triage.py                # phase 1 (both flows; keeps Langfuse tracking identical)
      answer_checker.py        # 9  (extracted)
      user_clarification.py    # 99 (extracted)
    conversation_flow/
      project_manager.py       # 2
      safety_gate.py           # 3
      cognitive_worker.py      # 4  (extracted from action_executor.py)
      mcp_operator.py          # 5  (extracted)
      data_engineer.py         # 6  (extracted)
      draft_writer.py          # 7
      editor_in_chief.py       # 8
    motion_flow/
      motion_planner.py        # NEW, id 20
      motion_validator.py      # NEW, id 21
  flows/
    conversation_flow.py       # steps + fast-path hook
    motion_flow.py             # steps + result builder (list of directives)

prompts/                       # FLAT
  capabilities.txt
  0_generic_prompt.txt ... 9_answer_checker.txt   (same names, moved up from advanced/)
  20_motion_planner.txt        # NEW
schema/response/               # advanced/ and basic/ untouched; motion-specific pieces added only if needed
config/step_models.json        # optional `flows` level; existing keys keep working
tests/                         # flat; test_motion_flow*.py and a structure test added
```

## Phase file constants (example)

```python
# phases/common/triage.py
PHASE_ID = 1
STEP_NAME = "triage_specialist"
PROMPT_FILE = "prompts/1_triage_specialist.txt"
SCHEMA_PIECES = ("intent", "user_goal", "task_category", "next_step")
DEFAULT_MODEL = GithubModels.GPT_4_1_MINI
FORMAT_NAME = "triage_specialist_phase1_response_format"
INTENT = ("clarification_request", ("information_request",), 1.0)
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_1"
```

`PROMPTS_DIR = "prompts"` is defined once. `PhaseSpec` carries these values, so the central dicts go away. `build_system_prompt` reads the phase's own prompt, `model_selection` and `metrics` build their tables from the registered phases. A structure test checks that each file in `phases/` defines exactly one phase with all the constants.

## Flows

- **Phase ids:** keep the existing ints; motion-flow uses 20-29. Step names are unique across flows.
- **Model config:** `step_models.json` gets an optional `flows` level (per-flow model per step). The current top-level keys remain the default and keep working. `AI_AGENT_MODEL_PHASE_<n>` keeps working.
- **Paused runs** record which flow they belong to, so a resume goes to the right flow.
- **Routes:** each flow has its own routes, and each route calls its own flow:
  - `/conversation-flow/session/start|message|end`
  - `/motion-flow/session/start|message|end`
  - `/session/*` stays as an alias to conversation-flow until Brain is updated.
- **Composition root** builds a `FlowRegistry`. A new agent = one flow file + its phase files + one registration line.

## motion-flow

Steps, one file each:

1. `triage` (common): classifies the request, tracked in Langfuse like conversation-flow.
2. `motion_planner` (id 20): works out what needs to move (arm, degrees, direction) as a structured list, validated by schema (no regex). If something is missing, the flow pauses and asks the user with the existing clarification mechanism, then resumes.
3. `motion_validator` (id 21): plain code, not an LLM call. Checks each command (valid arm, degrees range, valid direction) and the whole sequence (maximum number of commands, optionally a maximum total rotation). If any command is invalid, the whole sequence is rejected with a reason the robot can say. No half sequences.

Output: an ordered list, `directives: [MotorDirective, ...]` (for example left 90, then left -90). Brain executes them in order.

Open detail: `degrees` is signed today and there is also `direction` (`forward|reverse`), so "left -90" is ambiguous. Default: keep degrees signed, treat direction as explicit, and have the validator reject contradictions. Alternative: normalise to positive degrees plus direction. Confirm before step 4.

## Work order and gates

1. **Pure refactor, no behaviour change.** Constants in every phase file; extract phases 4, 5, 6, 9, 99; make `Pipeline` generic; move the conversation steps to `flows/conversation_flow.py`. Gate: all ai-agent tests pass and `tests/test_flow_golden.py` is unchanged and green.
2. **Move the prompts** up one level into flat `prompts/` and group phase files into `common/` and `conversation_flow/`. Same gate.
3. **`Flow` and `FlowRegistry` and per-flow routes**, with the `/session/*` alias. Gate: existing API tests pass.
4. **Build motion-flow** (planner, validator, list output, pause and resume) with mocked-LLM tests: single movement, sequences, missing details, impossible movement, sequence over the limit.
5. **Remove the robot code from conversation-flow**: `robot_directive.py`, the `robot_action` prompt and schema entries, the `directive` plumbing, the robot tests, and the arm lines in `capabilities.txt`. This is the one deliberate golden regeneration (`UPDATE_GOLDEN=1`); show the diff before accepting.
6. **Outside ai-agent:** `contracts` (motion module with the directive list, `robot_context` on the conversation request, version bump, re-bundle the wheel), Brain (call motion-flow first, forward the hint, execute directives in order; read Brain's current `directive` consumer first), `deployment/` docs and `robot.toml`, ai-agent `CLAUDE.md` and README.
7. **Full verification:** ai-agent tests, `brain_microservice\windows\Scripts\python.exe -m pytest contracts\tests -q` from the workspace root, and a `git status` comparison with the snapshot for unexpected files.

If any gate fails: stop and restore from the snapshot (`robocopy <snapshot>\<repo> <live>\<repo> /MIR /XD windows /XF .env` for each of the four folders, delete anything new, then compare `git status` and HEAD with the saved files).

## Risks

- Golden drift in step 1 is the main risk. No payload may be reordered or reworded.
- Extracting phases 4 to 6 from `action_executor.py` (dependency order, parallel actions) is the most delicate move.
- Paused runs must carry their flow.
- Brain's current consumption of `directive` has not been read yet.
- Phase ids and step names feed Langfuse and config, so they must stay unique and stable.

## Decisions taken

1. Prompts flat, each phase names its prompt in a constant.
2. motion-flow = triage, then planner (asks the user if details are missing), then validator.
3. Separate routes per flow, each calling its flow.
4. The output is a list of directives.

## As built (2026-09-30)

Verified: ai-agent 595 tests, Brain 152 (14 live tests skipped), contracts and the fake-hardware pipeline 48 (20 skipped: they need real LLM keys), deployment 232. The golden file changed only in the system prompt hash and length (59 calls), after the deliberate prompt edits.

Where it differs from the plan above:

- **Model config:** no `flows` level in `config/step_models.json`. Step names are unique across flows, so `motion_planner` is set by `steps`, a profile or `AI_AGENT_MODEL_PHASE_20` like any other step. `STEP_NAMES` (the cost, budget and ratings tables) stays conversation-flow's; `ALL_STEP_NAMES` also accepts `motion_planner`.
- **State:** motion-flow keeps its movements in `MotionFlowState` (a subclass of `FlowState`, `motion_state.py`), so the conversation state is unchanged. `Flow` has a `new_state` hook for that.
- **robot_context, not a hint in the prompts of the planner:** conversation-flow receives `robot_context` (`{directives, rejected_reason}`). With one it skips planning (triage, draft writer, editor), its triage never pauses, and the draft writer prompt explains how to word it. `RobotContext` and `AIAgentMotionMessageResponse` are in `contracts` 0.9.0, including `awaiting_user_input` (true when motion-flow's `response` is a question; Brain speaks it and does not ask conversation-flow).
- **Contracts:** `AIAgentMessageResponse.directive` is kept (always empty now) so an old caller does not break; remove it in a later contracts version.
- **Validator limits (my defaults, change the constants at the top of `motion_validator.py`):** at most 10 movements, 360 degrees per movement, 1440 degrees in total. A negative number of degrees with `reverse` is refused as ambiguous.
- **Phase ids:** motion planner 20, motion validator 21 (plain code, `LLM = False`).
- **Prompts:** flat `prompts/<id>_<name>.txt`; `prompts/advanced/` is gone. `capabilities.txt` is now neutral (the robot can move its arms; it no longer tells the agent to request a movement).
- **Brain:** `BrainService.decide()` asks motion-flow first, then conversation-flow; `HttpMotionAgentAdapter` is a new adapter; movements run in order through `move_arms()` and stop at the first failure. The stepper adapter sends a negative number of degrees as the same rotation in the opposite direction (stepper takes `abs()` of `rotations`, so before this "left -90" would have turned the arm forward). Brain env: `AI_AGENT_MOTION_{START_SESSION,MESSAGE,END_SESSION}_ENDPOINT`; the conversation endpoints now default to `/conversation-flow/session/...`.
- **Brain/ai-agent communication reworked (2026-10-01), replacing the Brain bullet above:** conversation-flow now runs FIRST and motion-flow only when it has ended (not the other way round). Brain keeps an ordered list of flows (`AI_AGENT_FLOWS`), one `AgentFlowPort` adapter per flow in a registry, one `AgentFlowSession` per flow, and `decide()` asks them one after the other; a flow that asks the user a question stops the chain and gets the next utterance. Because motion-flow runs after conversation-flow, Brain no longer sends `robot_context` (ai-agent and contracts still accept it): a refusal of motion-flow is spoken after the reply. The STT-to-TTS route says `message received` at once, `thinking` every 2 seconds while the flows run (`PROGRESS_*` settings) and only then the answer and the movements. The old `AI_AGENT_*_ENDPOINT` and `AI_AGENT_MOTION_*_ENDPOINT` settings are gone: the routes are `/<flow>/session/...`.
- **Other repos touched:** the new contracts wheel is vendored in all seven consumers (their requirements files name 0.9.0); `deployment` docs, `robot.example.toml` (regenerated) and `scripts/env_inventory.py` (descriptions of model phases 9 and 20).
- **Folder reorganisation (same day, after the plan above):** `application/orchestration/` has no loose files any more. `flows/` (conversation_flow, motion_flow, action_executor, fast_path, registry), `phases/` (the phase folders plus `catalog.py` and `phase.py`), `engine/` (pipeline, flow, phase_runner, clarification, answer_check), `state/` (flow_state, motion_state, paused_run) and `support/` (model_selection, metrics, failure, schemas, action_tree, mcp_servers, clock). `Pipeline` takes its flow as a required argument. `tests/test_orchestration_layout.py` keeps the dependencies one way. Paths in the sections above that say `phase_catalog.py` or `flow_registry.py` mean `phases/catalog.py` and `flows/registry.py` now. Snapshot before it: `D:\Hobbys\IA\OBLIVION_snapshots\pre_orchestration_reorg_2026-09-30`.
- **Found on the way:** `schema/response/general/actions/actions.schema.json` (the file the pipeline loads) never listed `robot_action` in its `action_type` enum, only a fragment file did, so a provider that enforces the schema could not produce it.
- **Not verified:** nothing ran against a real LLM or real stepper. `contracts/tests/e2e/test_real_pipeline.py` was updated for motion-flow (and a there-and-back scenario added) but is skipped without `E2E_REAL_LLM=1`.

Rollback (nothing was committed): restore the four folders from `D:\Hobbys\IA\OBLIVION_snapshots\pre_motion_split_2026-09-30` (plus `extra_consumers` for the vendor folders and requirements of the other five services), delete `docs\flows_refactor_plan.md` if unwanted, and reinstall the old contracts wheels in the two venvs I changed (ai-agent was on 0.7.1, Brain on 0.8.0): `pip install --no-deps --force-reinstall <snapshot>\<service>\vendor\contracts_microservice-0.8.0-py3-none-any.whl`.
