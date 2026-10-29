# Tasks

Hierarchical task plan, same format as `dynamics_microservice/docs/tasks`. Epics so far: **T-01 use the `dynamics_microservice` MCP tools from ai-agent** (in progress: everything but T-01.9, the maintainer's first real run, done on 2026-10-28; created 2026-10-27) and **T-03 Claude as a provider** (in progress: T-03.1 to T-03.5 done on 2026-10-28, T-03.6 run once; `docs/decisions/ADR-013-claude-through-sanitized-structured-outputs.md`) and **T-02 refresh the model catalog: no GitHub Models, Google free tier by default** (in progress: T-02.1, T-02.2 and T-02.4 to T-02.9 done on 2026-10-28; created 2026-10-27, plan in `docs/proposals/PR-004-model-catalog-gemini-free-tier.md`). It is written to be executed step by step: every leaf task states what to create or change, what it must not do and how to prove it is done.

The order, with the state and date of each task, is in [ORDER.md](ORDER.md). The board is in section 5. The prompts to start or resume the build in another session are in [PROMPTS.md](PROMPTS.md).

## 1. Structure and naming

- Every task is a Markdown file. A task with subtasks lives in a folder of the same name, and its own file has the same name inside that folder. Leaves are single files.
- IDs are hierarchical and stable: `T-01` -> `T-01.3`. Never reuse or renumber an ID.
- A parent describes goal, order and exit criteria; **leaves carry the implementation detail**.
- Every task file starts with a table: `Status`, `Kind`, `Parent`, `Depends on`, `Blocks`, `Size` (S, M, L), then *Goal*, *Files*, *Specification*, *Acceptance criteria*, *Verification* and, once started, *Notes*.

```text
docs/tasks/
├── README.md                                   (this file)
├── ORDER.md                                    the order, the state and the date of every task
├── T-01_dynamics-mcp/                          epic
│   ├── T-01_dynamics-mcp.md
│   └── T-01.1_decisions.md ... T-01.12_tool-call-metrics.md      leaves (T-01.10 to T-01.12 were added after Q03 and Q04)
├── T-02_model-catalog-refresh/                 epic
    ├── T-02_model-catalog-refresh.md
    └── T-02.1_decisions.md ... T-02.10_first-real-run.md         leaves
└── T-03_claude-provider/                       epic
    ├── T-03_claude-provider.md
    └── T-03.1_decisions.md ... T-03.6_first-real-run-on-claude.md leaves
```

## 2. Execution protocol

1. Pick the first task whose status is `todo` and whose `Depends on` tasks are all `done`. A `decision` task that is `awaiting-user` **stops the chain**: ask the user, record the answer in its *Resolution*, then continue.
2. Read `CLAUDE.md`, `docs/architecture/architecture.md` and the documents the task names before touching code.
3. Create or modify only the files listed under *Files* (tests included). Another file, folder or dependency means updating the task first.
4. Implement, then run the task's *Verification* and the baseline of section 3. A task is `done` only when every acceptance criterion passes.
5. Set its `Status` (and its row in section 5 and in `ORDER.md`), update the parent if its exit criteria are met, and record any new fact or deviation in *Notes*.
6. Never edit generated files by hand (the schema tree, `docs/models/*`).
7. All work of epic T-01 goes on the one branch `feature_dynamics_mcp` (no branch per task, Q04-5). Do not commit, push or open a pull request unless the user asks. Do not run anything that calls a real LLM or the real service without asking: it costs money.

Status values: `todo`, `awaiting-user`, `blocked`, `in-progress`, `done`.

## 3. Baseline definition of done (every code task)

- `python -m pytest tests` passes (mock-based, no keys, no network). The `windows` venv must exist; if it does not, create it with **Python 3.14** (`py -3.14 -m venv windows`, then `pip install -r requirements.txt`) and **ask once more right before installing** (Q04-7). The folder is git-ignored.
- `python scripts/split_schemas.py` reports no drift of the schema tree.
- A change to a prompt, schema, model or message format changes `tests/golden/flow_golden.json`: read the diff first, then regenerate on purpose (`UPDATE_GOLDEN=1`).
- The layering tests stay green (`test_orchestration_layout.py`, `test_phase_structure.py`); `domain/` imports nothing of the application, `application/` never imports `infrastructure/`.
- Keep the LLM adapter behind `LLMOutboundPort`; every phase file keeps its constants at the top.
- Code reads like the surrounding code: same comment density, naming and idiom.
- No secret, token or real customer data in code, tests, fixtures, prompts or documents; `.env` values are never printed. **No log line, metric or span holds a tool argument or a tool answer** (Q02-7). Hosts, tenants, environments and companies of Business Central are placeholders only.
- The documents that describe the change are true again (the table in `CLAUDE.md`).
- The Go project (`dynamics_microservice`) is **read-only** for this plan: never modify it.

## 4. Facts the tasks rely on

Verified on 2026-10-27 against both projects.

| # | Fact |
|---|---|
| F1 | `dynamics_microservice` serves MCP at `POST /mcp` (`MCP_PATH`) on the same port as its REST API: **Streamable HTTP**, stateless, plain JSON answers, no event stream; `GET` and `DELETE` answer 405; no authentication (`docs/api/mcp.md`, ADR-025 of that project). |
| F2 | Its tools: workflows `customer_orders`, `order_status`, `customer_card`; `list_workflows`, `get_guidance`, `get_job_result`, `cancel_job`; and, only with `MCP_EXPOSE_GENERIC_TOOLS=true` (default), `list_tables`, `describe_table`, `plan_query`, `run_query`. All read-only. |
| F3 | Every tool that reaches Business Central takes optional `environment` and `company`; the server defaults them (`MCP_ENVIRONMENT`, `MCP_COMPANY`). |
| F4 | A call waits up to `MCP_JOB_WAIT` (20 s) for its query; when it is not done the answer is `status: running` with a `job_id` and `next_offset`, read with `get_job_result`. |
| F5 | Answers are a few metadata lines (`returned`, `total`, `coverage`, `hint`) and a table delimited with `\|`, capped at 500 rows and 65,536 bytes. A failed call is a tool error `error (<kind>): <message>` with kind `input`, `not_found`, `retry_later`, `source_problem` or `internal`. |
| F6 | ai-agent MCP client: `SUPPORTED_TYPES = ("sse",)` in `infrastructure/outbound/mcp/config.py`; `client_manager.py` opens every session with `sse_client`; `tool_catalog.py` skips any type other than `sse`; one session per call. |
| F7 | `SERVER_TIMEOUT_SECONDS = 10` in `tool_catalog.py`, used by listing and by `tool_executor.py`, covers the whole session (connect, initialize, call). *Changed by T-01.4 (2026-10-27): the constant is now `LIST_TIMEOUT_SECONDS`, and a call uses `call_timeout_seconds()` (default 30).* |
| F8 | `mcps/*.json` are expanded with `${NAME}` by `expand_env`; a variable that is not set stays as written. `mcps/aws_microservice.json` is SSE at `http://localhost:8080/mcp/sse`; `fetch` and `filesystem` are stdio (skipped). |
| F9 | `prompts/capabilities.txt` ends with "No external service is connected"; the triage prompt's CAPABILITY CHECK treats any external service as impossible. *Changed by T-01.5 (2026-10-27): it now lists reading Business Central data through tools and ends "No other external service is connected"; the CAPABILITY CHECK only refuses a service the capabilities do not list.* |
| F10 | `task_category.domain` picks the flow; `data` (like any value other than `communication` and `movement`) goes to the special flow, whose project manager plans `mcp_tool_call` actions from the tool list. Phase 5 runs one action (one LLM call), phase 6 cleans the result. |
| F11 | Langfuse, when its keys are set, stores the user's text, the prompts and the answers of every call. For this epic that is accepted on purpose, with a trusted project, so the maintainer can see the data in the prototype (Q01-5 B, Q02-6 A). |
| F12 | A session keeps, for each earlier exchange, the user message and the reply that was sent (`AI_AGENT_HISTORY_TURNS`, default 6); triage and the project manager read them. Tool answers are not stored (Q04-1 A). |
| F13 | The MCP tool retry loop is in `application/orchestration/flows/action_executor.py` (`for attempt in range(max_attempts())`); `AI_AGENT_MAX_ATTEMPTS` (3) is shared with LLM calls and `retry` answers. *Refined by T-01.4 (2026-10-27): the loop re-asks the whole phase-5 step, not only the tool; a tool that failed for good stops it (`mcp_ports.watch_tool_failures`), and the tool call itself is retried once inside `MCPToolExecutor`.* |
| F14 | GitHub Models was **retired on 2026-07-30** (playground, model catalog, inference API and bring-your-own-key); GitHub names Azure AI Foundry and GitHub Copilot as the replacements (docs.github.com/en/github-models, read 2026-10-27). Foundry is a paid Azure service that needs an Azure resource, a model deployment and its own endpoint and key; it does not take a GitHub token. |
| F15 | The `DEFAULT_MODEL` of all 12 phase files is `GithubModels.GPT_4_1` or `GPT_4_1_MINI`. `get_selected_model` returns the first enum of the catalog that has the id (OpenAI, Google, Anthropic, Mistral, Cohere, Groq, Ollama, then GitHub), so `gpt-4.1-mini` and `gpt-4.1-nano`, priced as "openai" in `config/other_models.json`, route to GitHub. The active profile overrides the code default, so the retired default only runs when no profile is set. |
| F16 | Ten ids priced in `config/other_models.json` are not in the catalog: `claude-haiku-4-5`, `gpt-5-nano`, `gpt-5.4-mini`, `gpt-5.6-luna`, `gpt-5.6-terra`, `mistral-small-4-0-26-03`, `ministral-3-14b-25-12`, `mistral-large-3-25-12`, `deepseek-flash`, `deepseek-v4-pro`. The price loaders (`prices.py`, the three generators) read only `models`. |
| F17 | Google's pricing page (2026-10-27) gives a free tier for `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3-flash-preview` and `gemini-2.5-*` (which this project's key was refused on 2026-10-28: 404, no longer available to new users), and none for `gemini-4-argon` and `gemini-3.1-pro-preview`. Free-tier content is used to improve Google's products; its rate limits are not on that page. Paid prices: `gemini-3.1-flash-lite` 0.25 in / 1.50 out, `gemini-3.8-flash` 0.75 / 3.75 until 2026-12-31 then 1.50 / 7.50, `gemini-4-argon` 2.00 / 10.00 until 2026-11-30 then 4.00 / 20.00. |
| F18 | Anthropic's OpenAI-compatible endpoint (`https://api.anthropic.com/v1/`, what `ai_sdk`'s Anthropic provider uses) takes `response_format` of type `json_schema` only with `strict: true`: missing gives a 400 "strict: Field required", false a 400 "Input should be True". With it the model returns valid JSON for the schema. Anthropic's documentation says `response_format` is ignored: checked on 2026-10-28, it is not. Without a schema Claude wraps the JSON in code fences and invents values outside the enums. |
| F19 | Anthropic's structured outputs refuse an object without `additionalProperties: false`, number limits, `maxItems` and circular references ("action -> action"). The agent's actions schema is recursive (`subactions`), so the planner and the three action steps need it unrolled (T-03.2). The Claude 5.5 models do not support forced tool use and take no `top_p`; thinking is on by default and the endpoint hides it. |

## 5. Status board

| ID | Task | Kind | Status |
|---|---|---|---|
| [T-01](T-01_dynamics-mcp/T-01_dynamics-mcp.md) | **Use the dynamics_microservice MCP tools** (epic) | epic | in-progress (everything but T-01.9 done on 2026-10-28; T-01.9 is the maintainer's) |
| [T-01.1](T-01_dynamics-mcp/T-01.1_decisions.md) | Decisions | decision | done (2026-10-27) |
| [T-01.2](T-01_dynamics-mcp/T-01.2_streamable-http-transport.md) | Streamable HTTP transport in the MCP client | code | done (2026-10-28) |
| [T-01.3](T-01_dynamics-mcp/T-01.3_server-config-and-settings.md) | Server config and settings | code | done (2026-10-28) |
| [T-01.4](T-01_dynamics-mcp/T-01.4_mcp-timeouts.md) | Timeouts and retries that fit a slow query | code | done (2026-10-28) |
| [T-01.5](T-01_dynamics-mcp/T-01.5_capabilities-and-triage-prompts.md) | Tell the agent it has Business Central data | code | done (2026-10-28) |
| [T-01.6](T-01_dynamics-mcp/T-01.6_planner-guidance-and-jobs.md) | Planner: guidance, jobs and answers | code | done (2026-10-28) |
| [T-01.10](T-01_dynamics-mcp/T-01.10_server-availability.md) | Server availability: hide, cache, check, log | code | done (2026-10-28) |
| [T-01.11](T-01_dynamics-mcp/T-01.11_tool-call-cap.md) | Cap of MCP tool calls per message | code | done (2026-10-28) |
| [T-01.12](T-01_dynamics-mcp/T-01.12_tool-call-metrics.md) | Tool call metrics | code | done (2026-10-28) |
| [T-01.7](T-01_dynamics-mcp/T-01.7_verification.md) | Verification with scripted LLMs | test | done (2026-10-28) |
| [T-01.8](T-01_dynamics-mcp/T-01.8_documentation.md) | Documentation and ADR | docs | done (2026-10-28) |
| [T-01.9](T-01_dynamics-mcp/T-01.9_first-real-run.md) | First real run | manual | in-progress (run 2026-10-29: the tool path works; findings in its Notes) |
| [T-02](T-02_model-catalog-refresh/T-02_model-catalog-refresh.md) | **Model catalog refresh: no GitHub Models, Google free tier by default** (epic) | epic | in-progress (T-02.1, T-02.2 and T-02.4 to T-02.9 done on 2026-10-28; T-02.3 and T-02.10 done on 2026-10-28 with the Anthropic models; plan in [PR-004](../proposals/PR-004-model-catalog-gemini-free-tier.md)) |
| [T-02.1](T-02_model-catalog-refresh/T-02.1_decisions.md) | Decisions | decision | done (2026-10-27) |
| [T-02.2](T-02_model-catalog-refresh/T-02.2_profile-google-free.md) | Profile `google_free` | code | done (2026-10-28) |
| [T-02.3](T-02_model-catalog-refresh/T-02.3_confirm-ids.md) | Confirm the ids with the real key | manual | done (2026-10-28: free-tier Google ids and the six Anthropic ids; the paid-only Google ids dropped) |
| [T-02.4](T-02_model-catalog-refresh/T-02.4_catalog.md) | Catalog | code | done (2026-10-28) |
| [T-02.5](T-02_model-catalog-refresh/T-02.5_defaults-and-routing.md) | Defaults and routing | code | done (2026-10-28) |
| [T-02.6](T-02_model-catalog-refresh/T-02.6_prices-ratings-tokens.md) | Prices, ratings and token files | code | done (2026-10-28) |
| [T-02.7](T-02_model-catalog-refresh/T-02.7_tests-and-golden.md) | Tests and golden file | test | done (2026-10-28) |
| [T-02.8](T-02_model-catalog-refresh/T-02.8_generated-documents.md) | Generated documents | docs | done (2026-10-28) |
| [T-02.9](T-02_model-catalog-refresh/T-02.9_documentation.md) | Documentation and ADR | docs | done (2026-10-28) |
| [T-02.10](T-02_model-catalog-refresh/T-02.10_first-real-run.md) | First real run (on Claude since 2026-10-28) | manual | done (2026-10-28: the three messages on `claude_haiku` and `claude_mixed`, T-03.6) |
| [T-03](T-03_claude-provider/T-03_claude-provider.md) | **Claude as a provider** (epic) | epic | in-progress (T-03.1 to T-03.5 done 2026-10-28; T-03.6 run twice on 2026-10-28, the second with Sonnet all right; see [ADR-013](../decisions/ADR-013-claude-through-sanitized-structured-outputs.md)) |
| [T-03.1](T-03_claude-provider/T-03.1_decisions.md) | Decisions | decision | done (2026-10-28) |
| [T-03.2](T-03_claude-provider/T-03.2_sanitizer-and-wiring.md) | The schema sanitizer and its wiring | code | done (2026-10-28) |
| [T-03.3](T-03_claude-provider/T-03.3_tests.md) | Tests of the sanitizer and the wiring | test | done (2026-10-28) |
| [T-03.4](T-03_claude-provider/T-03.4_profile-and-price-notes.md) | The profile, the Claude notes in the price file and the generated tables | code | done (2026-10-28) |
| [T-03.5](T-03_claude-provider/T-03.5_documentation.md) | Documentation and ADR-013 | docs | done (2026-10-28) |
| [T-03.6](T-03_claude-provider/T-03.6_first-real-run-on-claude.md) | First real run on Claude | manual | in-progress (run twice on 2026-10-28; the second, with Sonnet, all right) |
