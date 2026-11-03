# T-05 — Structure: profiles, flows and steps as three pluggable layers

| | |
|---|---|
| Status | in-progress (created 2026-11-02; T-05.1 to T-05.7 done) |
| Kind | epic |
| Parent | project |
| Depends on | — (T-01 to T-04 are done) |
| Blocks | T-06 |

> Source: [PR-005](../../proposals/PR-005-flows-steps-profiles.md) (accepted by the maintainer on 2026-11-02 after the answers of Q05 to Q09) and [ADR-015](../../decisions/ADR-015-profiles-flows-steps.md). Read both before starting any task: this file does not repeat them.

## Goal

A client asks a **profile** on every request; a profile names one flow (or an ordered list of steps), its models, tools, prompts and inputs; a flow is an ordered list of steps; a step is one job declared in JSON. A new step, flow or profile is a set of files. **No prompt, schema or model changes in this epic**: where a task changes behaviour, its *Acceptance criteria* say exactly what.

## What exists and what changes

| Today | After T-05 |
|---|---|
| A flow is Python with a hard-coded list of steps (`flows/*.py`); one router chooses by `task_category.domain` | A flow is a JSON file; a profile names it; the service does not route, the client chains profiles |
| A "profile" is a table of models in `config/step_models.json`, global to all flows; `AI_AGENT_MODEL_PHASE_<n>` overrides | **Model sets** (the same tables) named by a profile at any level; the ordered list is also the fallback; no environment override |
| A message is one call; the answer is `response`, `directives`, `awaiting_user_input`, `flow` | The request gains `profile`, `token`, `inputs`, `return`, `pause_id`, `client`; the answer gains `profile`, `output`, `pause_id`, `discarded_pause` |
| The session keeps text pairs (`remember(message, reply)`) | The session keeps a list of `Response` objects |
| Steps are Python in `phases/`; each has constants at the top; `catalog.py` lists them | Steps are JSON declarations in `step_defs/`; Python only for `code` steps; a registry |
| The MCP list is the same for every step | Tools are limited by profile, flow and step (the narrowest wins) |
| Metrics by phase id | Metrics by profile, flow, step, model and client; the hash of the assembled profile |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-05.1 Decisions](T-05.1_decisions.md) | decision | done (2026-11-02) |
| 2 | [T-05.2 Step registry](T-05.2_step-registry.md) | code | done (2026-11-02) |
| 3 | [T-05.3 Folder layout](T-05.3_folder-layout.md) | code | done (2026-11-02) |
| 4 | [T-05.4 Config source port and file loader](T-05.4_config-source.md) | code | done (2026-11-02) |
| 5 | [T-05.5 Model sets, profile files and model resolution](T-05.5_model-sets-and-resolution.md) | code | done (2026-11-02) |
| 6 | [T-05.6 assemble() and its checks](T-05.6_assemble.md) | code | done (2026-11-02) |
| 7 | [T-05.7 The profiles of today's flows](T-05.7_profiles-of-todays-flows.md) | code | done (2026-11-03) |
| 8 | [T-05.8 Session list of Response](T-05.8_session-responses.md) | code | todo |
| 9 | [T-05.9 API: profile, token, inputs, return, pause_id](T-05.9_api.md) | code | todo |
| 10 | [T-05.10 Tests and golden of the profiles](T-05.10_tests-and-golden.md) | test | todo |
| 11 | [T-05.11 First real run: the `special` profile](T-05.11_first-real-run.md) | manual | todo |
| 12 | [T-05.12 Flows as JSON](T-05.12_flows-as-json.md) | code | todo |
| 13 | [T-05.13 Tool scoping](T-05.13_tool-scoping.md) | code | todo |
| 14 | [T-05.14 Prompts per profile](T-05.14_prompts-per-profile.md) | code | todo |
| 15 | [T-05.15 Metrics, profile hash and reserved data fields](T-05.15_metrics-and-hash.md) | code | todo |
| 16 | [T-05.16 Steps as JSON declarations](T-05.16_steps-as-json.md) | code | todo |
| 17 | [T-05.17 Commands and generated tables](T-05.17_commands-and-tables.md) | code | todo |
| 18 | [T-05.18 Documentation and ADR-015 accepted](T-05.18_documentation.md) | docs | todo |

The stages of PR-005 section 11 map to tasks: S1 = T-05.2 and T-05.3; S2 = T-05.4 to T-05.11; S3 = T-05.12; S4 = T-05.13; S5 = T-05.14; S6 = T-05.15; S7 = T-05.16 and T-05.17.

## Exit criteria

- Every profile of PR-005 section 11 loads, passes `assemble()` and answers on mocks; the golden file has one block per profile `identification`, `chat`, `special`, `movement`, `gesture` and every request equals today's request of the same step (S1, S3, S7: the file is byte-identical; S2: the blocks are the new ones and the diff was read first).
- **Adding a profile is one file; adding a step is one JSON file and a prompt**, shown by a test that does both on a temporary folder.
- The acceptance run of T-05.11 passed with the real models and the Dynamics service up.
- The API, the request and the answer fields are documented in `docs/api/api.md`; the documents of the table in `CLAUDE.md` are true; ADR-015 is Accepted and ADR-003, ADR-004 and ADR-014 carry a dated note.

## Rules that bind every task of this epic

- Dependencies go one way: profile -> flow -> step -> catalog; a step never names a flow or a profile (PR-005 section 3). The layering test is rewritten in T-05.3 and stays green.
- Behaviour changes only where a task says so. A task that changes the golden file reads the diff first and regenerates on purpose (`UPDATE_GOLDEN=1`).
- A token is never written to a log, a metric, a span, a test fixture or a document; `token_sha256` holds a hash (PR-005 section 3.4). No tool argument or answer in any log (`CLAUDE.md`).
- Python code reads like the surrounding code. The generated files are not edited by hand.
- No real LLM call and no call to the real Dynamics service except in T-05.11, and only when the maintainer says so. Commit and push only when asked. The branch is `feature_reorganitzation` (Q05-23 default; one pull request per stage: S1, S2, S3, S4, S5, S6, S7).
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- Brain and the `contracts` repository are the maintainer's, later: this epic changes ai-agent and its documents only.
- The data policy (Q07-16) is not built; T-05.15 only reserves the fields.
