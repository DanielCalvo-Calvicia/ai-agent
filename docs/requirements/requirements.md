# Requirements

Status as of 2026-10-27, taken from `CLAUDE.md`, `README.md` and the code after the merge of PR #3 (the four-flow redesign and the expression flow) and epic T-01 (the Dynamics tools, built on the branch `feature_dynamics_mcp`, T-01.2 to T-01.8). **Done** means built and covered by the mock-based tests; **Not verified** means built but never run against a real LLM or the real service. Nothing here has run against a real LLM since the redesign.

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
| FR-14 | Use MCP tool servers (SSE, Streamable HTTP) from the special flow; each new Streamable HTTP server is one JSON file in `mcps/` | Done (Not verified with a real server): `type: sse` and `type: streamable_http` work; stdio servers are skipped; nothing uses `aws_microservice` yet | [configuration](../configuration/environment-variables.md), ADR-011 |
| FR-17 | Read Business Central data (the orders of a customer, the state of an order, a customer card) through the tools of `dynamics_microservice`, read-only: only the tools of `allowed_tools`, no environment or company sent, no confirmation, the reply in the language of the user in plain text, no row limit of ours, a `running` answer followed up once, a tool error told in one honest sentence, a missing customer code asked | Done with scripted LLMs and a local fake of the service (Not verified with a real model or the real service: T-01.9) | ADR-011, [api](../api/api.md) |
| FR-18 | Bound the tool calls: a call limit (`AI_AGENT_MCP_CALL_TIMEOUT_SECONDS`), 60 s of waiting in total per message, one retry only after a transport error or `retry_later`, a cap of tool actions per message (`AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`), a server that is down hidden (a failed listing is not retried for 60 s) and an optional reachability check that only logs | Done | ADR-011, [configuration](../configuration/environment-variables.md) |
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
| NFR-7 | No secret in code, tests, fixtures or documents; no host, tenant, company or customer code of Business Central (placeholders only) | Done (by rule) | [security](../security/security.md) |
| NFR-8 | Latency suitable for a voice reply | Not met with `gemini-2.5-flash` (a model Google no longer gives to new keys; triage alone took 3 to 14 s on 2026-09-21); a lighter model or thinking turned off is needed. Not measured since | [proposals/PR-003](../proposals/PR-003-orchestrator-review/decisions.md) |
| NFR-9 | No log line, metric or span holds a tool argument or a tool answer: only the tool name, the outcome, the duration and the tries | Done, enforced by the whole-message log tests of `tests/test_mcp_dynamics_flow.py` (checked with a stand-in for `shared-logging`) | [monitoring](../operations/monitoring.md) |

## Known gaps

1. One real run since the four-flow redesign, on 2026-10-28 (T-02.10): three messages answered correctly on `gemini-3-flash-preview` (a throw-away profile); the active profile `proven` could not finish because Google answered 503 "high demand" for `gemini-3.1-flash-lite` that day. No real run of the Business Central tools (T-01.9).
2. Routing is only as good as triage's `domain`; a message that mixes a reply and a movement goes to one flow only.
3. stdio MCP servers are not supported, but the project manager is told they exist.
4. `constraints`, `mcp_routing` and `missing_information` have schemas and domain objects, but no phase writes them; `next_step.retry_action_id` is read and nothing acts on it.
5. The movement flow was exercised only with scripted LLMs and fake hardware.
6. The tools of `dynamics_microservice` were exercised only with scripted LLMs and a local fake server: no real model has been asked to pick a tool, follow a `running` answer up or word an error (T-01.9).
7. `SessionService` builds a `MessageFlowService` (a router and four pipelines) per message.
8. The rate limits of the Google free tier are not published on Google's pricing page. Measured once on 2026-10-28 with this project's key (T-02.3): `gemini-3.1-flash-lite` answered 10 calls in a row; `gemini-3.6-flash` answered 7 calls in about 30 s and then returned 429 "quota exceeded", and answered again 25 s later (about 6 to 7 requests per minute). There is also a **daily limit**: for `gemini-3-flash-preview` Google answered 429 "Generate content requests per day limit exceeded on Free Tier, limit: 20" (per project and model, retry in about 16 h), reached on 2026-10-28 after about 20 calls, so a free key gives only a few messages a day on a model. One message makes about 4 to 8 calls, most of them to the flash model, so a message with a plan can reach the per-minute limit; failed calls are retried (`AI_AGENT_MAX_ATTEMPTS`) without waiting. Not measured with a whole message (T-02.10, [ADR-012](../decisions/ADR-012-gemini-free-tier-default-no-github-models.md)).
9. Prices are not dated: `gemini-3.8-flash` and `gemini-3.6-flash` double on 2027-01-01 and `gemini-4-argon` on 2026-12-01, and the cost tables use one price per model (`prices.py`).
10. `google_free` costs about $0.20 per big-plan message at paid prices (about 175 EUR per 1,000 messages) against the 50 EUR budget; on the free tier it costs nothing. The thinking tokens of the estimate are guesses until T-02.10.
11. The Gemini ids were checked once with the real key on 2026-10-28 (T-02.3), only those with a free tier: `gemini-3.8-flash` did not answer (503, capacity), and `gemini-3.1-pro-preview` and `gemini-4-argon` were not called (no free tier; `gemini-4-argon` is in the price file marked "not called"). Mistral has no selectable model.
12. Claude (profile `claude_haiku`, ADR-013) ran once on 2026-10-28: three messages, 10 calls, 0 errors, about 2.7 cents (T-03.6); never on a plan or a tool call. On Claude the planner nests at most 3 levels, the strict schema adds about 2.8k input tokens to each call of the four actions steps, and Claude 5 thinks by default with the endpoint hiding it, so the cost tables understate the planner. Anthropic documents its OpenAI-compatible endpoint as for testing, not production.
13. On `claude-haiku-4-5` the greeting "Hello! How are you today?" was answered with a description of the reply ("A warm and friendly conversational response acknowledging the greeting...") instead of the reply: the draft writer copied the `expected_outcome` of triage. Not fixed in the profile `claude_haiku`. With `claude-sonnet-5-5` on the draft writer and the editor (a throw-away profile, 2026-10-28) the same greeting got a real reply, and the planner on Sonnet ran a plan (13 calls, 0 errors, about 6.6 cents for the three messages); one sample, so reword the draft writer's prompt if the wrong reply comes back on Haiku (T-03.6).

## Known limits of the Dynamics tools (accepted for the prototype, ADR-011)

1. **No authentication in either service.** The Go endpoint is open and reached by a public IP and port over plain HTTP. Who may see which customer is decided above ai-agent; a Cognito identity service is planned.
2. **No masking** of the data sent to the language model provider or to Langfuse. Langfuse receives the user's text, the prompts and the answers (the tool results included) on purpose in the prototype phase, in a project the maintainer trusts; later the data moves to a more secure store.
3. **No row limit in ai-agent.** Some requests will return many rows; the Go service caps at 500 rows and 64 KB.
4. The data policy of the enterprise account of the model provider is `UNKNOWN`; the first real run uses a test customer. The timeout of the caller of ai-agent is `UNKNOWN` until it is measured (T-01.9).
5. The mixture of the robot and a generic client (a web chat) needs refinement: the prompts say "the user" in the new lines, but the robot-specific lines stay.
6. When every MCP server is hidden, the answer schema still lets `mcp_context.server_id` be any string; only the project manager prompt steers it. The cognitive worker prompt does not yet say that a tool result it receives is data.
