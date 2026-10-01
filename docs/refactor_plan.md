> **HISTORICAL (banner added 2026-10-01).** The 2026-09-21 refactor plan, done. The `application/orchestration/` paths in it were reorganised afterwards into `flows/`, `phases/`, `engine/`, `state/`, `support/` (see `flows_refactor_plan.md` and `README.md`).

# ai-agent: refactor plan

Goal: reorganize the agent (mainly the orchestrator of the phases) **without changing what it does**, then fix the known bugs as separate, deliberate steps.

## Status (2026-09-21)

Refactor: **done**, checked by `tests/test_flow_golden.py` (7 scenarios, identical LLM calls before and after). Two deviations from the plan below:
- No `MeteredLLM` wrapper. `PhaseRunner.send` records the tokens, which is also a single place, and a wrapper would have needed to smuggle the phase and action id through `Payload.metadata`.
- `SessionService` still builds a `MessageFlowService` (and its pipeline) per message, because metrics are per message. It is cheap.

One deliberate behavior change happened during the fixes, and the golden file was regenerated for it: prompts were read with the Windows code page, so the em dash of `0_generic_prompt.txt` reached the LLM as `â€”`. They are now read as UTF-8. This is the only difference in the recorded calls (system prompt text of every phase).

Bug fixes (section 5): 1 done, 2 not a bug, 3 done, 4 done, 5 done, 6 done for SSE servers (stdio not supported), 7 done, 8 done, 9 done, 10 done, 11 done. Nothing was run against a real LLM. See `README.md`, "Known problems and decisions" for what is still open.

Extra findings while fixing:
- Phase 5 passed MCP server configs (dicts) where the adapter expected tool objects, so it would have crashed on the first real MCP action. The adapter now expands a server descriptor into that server's tools.
- `tests/message_service.py` was collected by pytest and would have called the real LLM. It moved to `tests/manual/`.
- `test_message_received_success` was already failing before this work (its mock predates the multi-phase flow). Fixed.

## Second pass: one job per file (2026-09-21)

Applied SRP / DIP file by file, behavior unchanged (golden test and 100+ tests green):
- `infrastructure/outbound/llm/vercel.py` (548 lines) became `vercel.py` (adapter only), `config.py`, `provider_models.py` (a table of routes instead of an if-chain, so a provider is one row), `tools.py`, `response_mapper.py`. Removed unused code: streaming, audio, chat history, `set_model`, session id and start/stop lifecycle.
- `domain/entities/response.py` no longer parses JSON. The parsing moved to `response_mapper.py`, one function per section. Removed its unused validation and helper methods.
- Domain no longer reads files. The 52 `get_*schema*` functions and path constants were removed. `application/orchestration/schemas.py` loads schemas by name (cached, independent of the working directory).
- `domain/value_objects/model.py` split into `model_catalog.py` (ids) and `model.py` (`SelectedModel`). The notes string moved to `docs/model_catalog_notes.md`.
- `session_service.py` lost the conversation-flow bookkeeping (it stored every conversation forever and nothing read it) and the duplicate MCP loader. `user_session.py` holds a session.
- `fastapi.py` split from `responses.py` (envelope). The three routes share one handler.
- MCP: `tool_catalog.py` (which tools, which server) split from `tool_executor.py` (run a tool). Removed the placeholder `get_session`.
- `phase_runner.py` lost `model_for_phase` (`model_selection.py`) and the prompt assembly (`system_prompts/advanced.py`). The two payload builders share `_build_payload`. `action_tree.py` holds the tree helpers.
- Deleted dead code: domain `Session`, `Conversation`, `ConversationHistory`, `FlowResponse`, `User`, and the `email`, `password`, `token` value objects (only `User` used them).

The plan as originally written follows.

Rule for the whole plan: a refactor step must not change behavior, and a bug fix must not be mixed into a refactor step. Otherwise a regression cannot be told apart from a fix.

## 1. Why refactor

`application/service/message_flow_service.py` has 1077 lines and does seven jobs:

| Job | Where today | Problem |
|---|---|---|
| Phase ordering and pause logic | `main_flow` | Fine in itself, but buried with everything else. |
| Building the LLM request | `phase1..8_*` methods | The same ~60 lines are copied 8 times. Only model, schema fields and input dict differ. |
| Walking the action tree | `_process_action_recursive`, `_normalize_action_recursive` | Shared by phases 4, 5 and 6 but tangled with the phase methods. |
| Token tracking | `_track_response` called by hand in each phase | Easy to forget in a new phase. |
| Clarification question (phase 99) | `_synthesize_user_clarification` | A whole extra LLM call inlined in the service. |
| State | mutable `self.flow_response`, overwritten piece by piece | Hard to see what each phase reads and writes. No place for conversation history. |
| Lifetime | a new `MessageFlowService` per message | Prompts, config and the pipeline are rebuilt every time. |

Adding a phase, changing a model or adding memory currently means editing many places in one huge file.

## 2. Target structure

```text
application/orchestration/
  flow_state.py       FlowState dataclass (replaces self.flow_response)
  phase.py            PhaseSpec + Step definitions
  phase_runner.py     the only place a Payload is built and sent
  action_walker.py    depth-first action recursion (phases 4, 5, 6)
  pipeline.py         the orchestrator (about 40 lines)
  clarification.py    phase 99
  metrics.py          SessionMetrics, TokenCount, RequestRecord (moved as is)
  prompts.py          phase name -> prompt file, cached
  phases/
    triage.py  project_manager.py  safety_gate.py  cognitive_worker.py
    mcp_operator.py  data_engineer.py  draft_writer.py  editor_in_chief.py
application/service/message_flow_service.py   thin adapter: text() -> pipeline.run()
```

Dependencies point inward only: `orchestration` uses `LLMOutboundPort` and `domain`, never `infrastructure`. `domain/`, `schema/`, `prompts/advanced/*.txt` and the HTTP layer do not change.

### 2.1 FlowState

One object that travels through the pipeline instead of `self.flow_response`.

```python
@dataclass
class FlowState:
    message: str
    intent: Optional[Intent] = None
    user_goal: Optional[UserGoal] = None
    task_category: Optional[TaskCategory] = None
    actions: Optional[List[Action]] = None
    next_step: Optional[NextStep] = None
    safety_and_validation: Optional[SafetyAndValidation] = None
    constraints: Optional[Constraints] = None
    history: List[Message] = field(default_factory=list)   # unused now, ready for memory
```

Why: each phase declares what it reads and what it writes, and memory later becomes a field, not a rewrite.

### 2.2 PhaseSpec

Each phase is data plus two small functions.

```python
@dataclass(frozen=True)
class PhaseSpec:
    id: int
    name: str                      # "project_manager"
    model: GithubModels            # same defaults as today
    temperature: float             # 1.0 today
    max_tokens: int                # 10000 today
    intent: tuple[str, list[str], float]
    output_fields: dict            # schema pieces for response_format
    build_input: Callable[[FlowState, "PhaseContext"], Any]
    apply: Callable[[FlowState, Response], None]
```

Example (phase 3):

```python
safety_gate = PhaseSpec(
    id=3, name="safety_quality_gatekeeper", model=GithubModels.GPT_4_1,
    output_fields={"safety_and_validation": ..., "next_step": ...},
    build_input=lambda s, c: {"actions": s.actions, "next_step": s.next_step},
    apply=lambda s, r: (setattr(s, "safety_and_validation", r.safety_and_validation),
                        setattr(s, "next_step", r.next_step)),
    ...
)
```

Why: the differences between phases become visible in one glance, and a new phase is one new file.

### 2.3 PhaseRunner

The only code that builds a `Payload`: system prompt (generic phase 0 + phase prompt), user message, `ResponseFormat` from `output_fields`, then `outbound_port.ask()`. It replaces the eight copied blocks.

Token tracking moves here through a `MeteredLLM` wrapper around `LLMOutboundPort` that records each call into `SessionMetrics`. Phases no longer call `_track_response`.

### 2.4 ActionWalker

The current recursion, moved as is, parameterized by `phase`, `skip_type`, `only_type`, `extra_context` and `tools`. Phases 4, 5 and 6 become three `PhaseSpec`s that the runner hands to the walker. Behavior kept: depth first, subactions before parents, `completed_outputs` shared, MCP actions marked blocked when confirmation is required.

### 2.5 The orchestrator (`pipeline.py`)

```python
PIPELINE = [
    Step(triage),
    Step(project_manager, pause_if=needs_user_input),
    Step(safety_gate,     pause_if=needs_user_input),
    Step(cognitive_worker),
    Step(mcp_operator),
    Step(data_engineer),
    Step(draft_writer),
    Step(editor_in_chief),
]

class Pipeline:
    def run(self, message: str) -> str:
        state = FlowState(message=message)
        for step in PIPELINE:
            self.runner.execute(step, state)
            if step.pause_if and step.pause_if(state):
                return self.clarifier.ask(state)     # phase 99
        return state.final_text()                    # user_goal.expected_outcome or ""
```

`needs_user_input` is today's `_requires_user_input` (status `awaiting_user_input` or `awaiting_confirmation`). `final_text()` keeps the current return rule.

### 2.6 Session wiring

`SessionService` builds the `Pipeline` once and calls `run()` per message. The public API and DTOs do not change. Per-message metrics still exist (one `SessionMetrics` per run, as today).

## 3. Steps, in order

Each step ends with the golden test passing and no other change.

1. **Golden test (before touching code).** Add `tests/test_flow_golden.py`. A scripted mock `LLMOutboundPort` returns canned JSON per phase. It records every call as `(phase, model, system prompt, user message string, response_format, temperature, max_tokens, tools)`. Run it against the **current** code and save the sequence and the final reply as a golden file. Cover at least: the simple path (all 8 phases), a pause after phase 2, a pause after phase 3, an action tree with subtasks and dependencies, and an MCP action with and without required confirmation.
2. **`metrics.py`.** Move `TokenCount`, `RequestRecord`, `SessionMetrics` unchanged. Add `MeteredLLM`.
3. **`PhaseRunner` + `PhaseSpec`.** Move phases 1, 2, 3, 7, 8 (whole-response) one at a time.
4. **`ActionWalker`.** Move the recursion and phases 4, 5, 6.
5. **`clarification.py`.** Move phase 99.
6. **`pipeline.py`.** Replace `main_flow` with the pipeline loop. `MessageFlowService.text()` calls it.
7. **`SessionService`.** Build the pipeline once. Delete the old service body.

## 4. Things to keep exactly as they are

These look like quirks but the golden test depends on them. Change them later, on purpose:

- The user message is `dict.__str__()`, not JSON.
- Temperature 1.0, max tokens 10000 (2000 and 0.7 for phase 99), `gpt-4.1-mini` for phase 1, `gpt-4.1` elsewhere.
- Intent values passed in each payload.
- Recursion order and the `completed_outputs` handling.
- The fallback message when nothing is required from the user.

## 5. After the refactor: bug fixes (one change each, each with a test)

| # | Fix | Why | How |
|---|---|---|---|
| 1 | Load `.env`, fix key names | Keys are never read unless already in the environment. `OPRENAI_API_KEY` is a typo and `GITHUB_PAT` vs `GITHUB_API_KEY` disagree. | `load_dotenv` in `main.py` (add `python-dotenv`), one `Settings` class reading the names listed in `.env.example`. |
| 2 | Correct provider class | GitHub, Google, Mistral, Groq and Cohere use `AnthropicModel`. | Check the `ai_sdk` provider API. Use its OpenAI-compatible model with the base URL. Verify with one real call (costs money, ask first). |
| 3 | Ollama `KeyError` | `PROVIDER_BASE_URLS["OLLAMA_URL"]` does not exist. | Add the key or read `Config.OLLAMA_URL`. |
| 4 | Do not block the event loop | `async def` routes call a synchronous 6+ call chain, freezing the service and any `/health`. | `await anyio.to_thread.run_sync(pipeline.run, ...)` in the route or the service. |
| 5 | `GET /health` | Workspace rule. | Same envelope as the other services. |
| 6 | MCP wiring | `tool_executor` is never set, so phase 5 gets a mock result. `fetch` and `filesystem` are stdio, which the client cannot run. | Build `MCPClientManager` + `MCPToolExecutor` in `main.py` and pass it in `VercelAIConfig`. Add stdio support or drop those two configs. Make the filesystem path configurable. |
| 7 | Memory | Every message starts from zero. Paused flows (`awaiting_user_input`) are not resumed. | Use `FlowState.history`, store it per session, feed it to phases 1 and 2. Resume a paused flow on the next message. |
| 8 | Error handling | Exception text is returned as the reply text. Brain could speak it. | Return an error status and an empty reply, log the details. |
| 9 | Config for models | Model ids are hardcoded per phase. | Read overrides from env variables. Defaults stay the same. See `docs/model_recomended_per_phase.md`. |
| 10 | Paths | Prompts and `mcps/` are found relative to the current directory. | Resolve from the project root (`Path(__file__)`). Open files with `encoding="utf-8"`. |
| 11 | Convention gaps | No `.env.example`, unpinned `requirements.txt`, tests mixed with manual scripts. | Add `.env.example` (names only), pin versions, move manual scripts to `tests/manual/`. |

## 6. After that: Brain integration

- Latency: six or more sequential LLM calls is too slow for voice. Consider a fast path for simple chit-chat (skip phases 2 to 6 when triage says no actions are needed). This changes behavior, so it is a decision for later.
- Contract: decide whether the session API moves into `contracts.api`. Do not change it unasked.
- Brain calls `POST /session/message` between STT and TTS. Brain keeps the only coordination role. `ai-agent` only returns text.

## 7. Done means

- Golden test passes after every refactor step.
- `pytest tests` passes with the mock LLM (no keys, no cost).
- The old `message_flow_service.py` is under about 50 lines.
- Adding a new phase requires one new file in `orchestration/phases/` and one line in `PIPELINE`.
- Real LLM calls are only made after asking, since they cost money.
