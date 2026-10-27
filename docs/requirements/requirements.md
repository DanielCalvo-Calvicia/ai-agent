# Requirements

Status as of 2026-10-27, taken from `CLAUDE.md`, `README.md` and the code after the merge of PR #3 (the four-flow redesign and the expression flow). **Done** means built and covered by the mock-based tests; **Not verified** means built but never run against a real LLM. Nothing here has run against a real LLM since the redesign.

## Functional

| ID | Requirement | Status | Record |
|---|---|---|---|
| FR-1 | Receive what the user said (text) and return a structured answer: what to say, which arm movements to run, whether it waits for the user, and which flow answered | Done (Not verified with a real LLM) | [api](../api/api.md) |
| FR-2 | Never control hardware and never call stepper, TTS or speaker; Brain acts on the answer | Done | ADR-002 |
| FR-3 | Brain makes one call per utterance | Done | ADR-003 |
| FR-4 | Every message goes through the identification flow (triage); `task_category.domain` picks one flow: `communication` -> conversation, `movement` -> movement, anything else -> special | Done (routing quality Not verified: it depends on triage) | ADR-004 |
| FR-5 | The flows never call each other; only the router hands the identification state to the next flow, so nothing is classified twice | Done | ADR-004 |
| FR-6 | A flow that asked the user a question is resumed by the next message without identifying it again (answer, yes, no, not an answer, stop) | Done | architecture 4.3 |
| FR-7 | Conversation flow: draft writer, then editor; special flow: project manager, safety gate, action executor (cognitive worker, MCP operator, data engineer), draft writer, editor | Done | architecture 4 and 5 |
| FR-8 | Movement flow: motion planner (LLM) and motion validator (plain code): valid arm and direction, degrees within limits, at most 20 movements and 3600 degrees in total; one bad movement refuses the whole sequence | Done | architecture 5 |
| FR-9 | `response` is always speakable: an apology on failure; empty only for a movement that goes ahead with `speak_movements` off; a refusal or a question is always said | Done | [api](../api/api.md) |
| FR-10 | Expression flow (`AI_AGENT_EXPRESSION`, default on): after a conversation or special reply, one cheap model call reads the emotion and plain code builds a random arm gesture shaped by it, about as long as the speech, every arm back where it started; it never holds back the reply | Done | ADR-007 |
| FR-11 | Sessions with history (`AI_AGENT_HISTORY_TURNS`, default 6), in process memory | Done | ADR-009 |
| FR-12 | Which model answers each step is configurable per phase: environment variable, then `config/step_models.json`, then the active profile, then the code default | Done | [configuration](../configuration/environment-variables.md) |
| FR-13 | Independent actions of a plan can run together (`AI_AGENT_PARALLEL_ACTIONS`); a failed action never stops the others | Done | architecture 8 |
| FR-14 | Use MCP tool servers (SSE) from the special flow | Partly done: only `type: sse` works; stdio servers are skipped; nothing uses `aws_microservice` yet | [configuration](../configuration/environment-variables.md) |
| FR-15 | Report cost and usage to Langfuse when its keys are set | Done | [monitoring](../operations/monitoring.md) |
| FR-16 | Keep the LLM adapter behind `LLMOutboundPort` so providers stay swappable; add a provider with one row | Done | ADR-010 |

## Non-functional

| ID | Requirement | Status | Record |
|---|---|---|---|
| NFR-1 | Layers: `domain` imports nothing of the application, `application` never imports `infrastructure`, `composition_root` is the only place that knows every layer; inside orchestration the dependencies go one way | Done, enforced by `tests/test_orchestration_layout.py` | architecture 2 and 3 |
| NFR-2 | One phase per file, constants first; every referenced prompt and schema exists | Done, enforced by `tests/test_phase_structure.py` | architecture 5 |
| NFR-3 | The schema tree is generated from `full.schema.json`; nothing else is edited by hand | Done, enforced by `tests/test_schema_tree.py` | ADR-005 |
| NFR-4 | Every LLM call (model, prompts, messages, schema, sampling, tools) is pinned by a golden file; a change is read and regenerated on purpose (`UPDATE_GOLDEN=1`) | Done | `tests/test_flow_golden.py` |
| NFR-5 | The tests run without keys, network or cost; `tests/manual/` scripts call real services and are not collected | Done | [deployment](../deployment/deployment.md) |
| NFR-6 | Logging and tracing through `shared_logging`; trace headers forwarded to MCP servers | Done | [monitoring](../operations/monitoring.md) |
| NFR-7 | No secret in code, tests, fixtures or documents | Done (by rule) | [security](../security/security.md) |
| NFR-8 | Latency suitable for a voice reply | Not met with `gemini-2.5-flash` (triage alone took 3 to 14 s on 2026-09-21); a lighter model or thinking turned off is needed. Not measured since | [proposals/PR-003](../proposals/PR-003-orchestrator-review/decisions.md) |

## Known gaps

1. No real LLM call since the four-flow redesign.
2. Routing is only as good as triage's `domain`; a message that mixes a reply and a movement goes to one flow only.
3. stdio MCP servers are not supported, but the project manager is told they exist.
4. `constraints`, `mcp_routing` and `missing_information` have schemas and domain objects, but no phase writes them; `next_step.retry_action_id` is read and nothing acts on it.
5. The movement flow was exercised only with scripted LLMs and fake hardware.
6. `SessionService` builds a `MessageFlowService` (a router and four pipelines) per message.
