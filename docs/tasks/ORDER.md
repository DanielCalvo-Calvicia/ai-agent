# Task order

The order in which the tasks must be done, with the state of each one and the date its file was last updated. It follows the execution protocol of the [tasks README](README.md) (section 2): the first task that is `todo` and whose dependencies are `done`.

**Keep this file true:** every change to a task (a status, a dependency, a new task, an order change) updates this table, the board of the [tasks README](README.md) section 5 and the task file itself.

## States

| State | Meaning |
|---|---|
| Done | Implemented and verified (or, for a decision, taken and recorded) |
| In progress | Some of its subtasks are done and some are not |
| Todo | Ready to start when its dependencies are done |
| Awaiting user | A decision needs an answer; it stops the chain |
| Blocked | Waits for another task or for a decision |

Written on 2026-10-27.

## A. T-01 Use the dynamics_microservice MCP tools

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 1 | [T-01](T-01_dynamics-mcp/T-01_dynamics-mcp.md) | Use the dynamics_microservice MCP tools (epic) | epic | Done | T-01.9 ran on 2026-10-29; its open findings are in its notes | — | 2026-10-28 |
| 2 | [T-01.1](T-01_dynamics-mcp/T-01.1_decisions.md) | Decisions | decision | Done | decided in Q01 and Q02 (2026-10-27) | — | 2026-10-27 |
| 3 | [T-01.2](T-01_dynamics-mcp/T-01.2_streamable-http-transport.md) | Streamable HTTP transport in the MCP client | code | Done | built 2026-10-27, closed 2026-10-28 | — | 2026-10-28 |
| 4 | [T-01.4](T-01_dynamics-mcp/T-01.4_mcp-timeouts.md) | Timeouts and retries that fit a slow query | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.2 | 2026-10-28 |
| 5 | [T-01.3](T-01_dynamics-mcp/T-01.3_server-config-and-settings.md) | Server config and settings | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.2 | 2026-10-28 |
| 6 | [T-01.10](T-01_dynamics-mcp/T-01.10_server-availability.md) | Server availability: hide, cache, check, log | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.2, T-01.3 | 2026-10-28 |
| 7 | [T-01.11](T-01_dynamics-mcp/T-01.11_tool-call-cap.md) | Cap of MCP tool calls per message | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.2 | 2026-10-28 |
| 8 | [T-01.12](T-01_dynamics-mcp/T-01.12_tool-call-metrics.md) | Tool call metrics | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.2, T-01.4 | 2026-10-28 |
| 9 | [T-01.5](T-01_dynamics-mcp/T-01.5_capabilities-and-triage-prompts.md) | Tell the agent it has Business Central data | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.3 | 2026-10-28 |
| 10 | [T-01.6](T-01_dynamics-mcp/T-01.6_planner-guidance-and-jobs.md) | Planner: guidance, jobs and answers | code | Done | built 2026-10-27, closed 2026-10-28 | T-01.5, T-01.10, T-01.11 | 2026-10-28 |
| 11 | [T-01.7](T-01_dynamics-mcp/T-01.7_verification.md) | Verification with scripted LLMs | test | Done | built 2026-10-27, closed 2026-10-28 | T-01.2 to T-01.6, T-01.10 to T-01.12 | 2026-10-28 |
| 12 | [T-01.8](T-01_dynamics-mcp/T-01.8_documentation.md) | Documentation and ADR | docs | Done | built 2026-10-27, closed 2026-10-28 | T-01.2 to T-01.6, T-01.10 to T-01.12 | 2026-10-28 |
| 13 | [T-01.9](T-01_dynamics-mcp/T-01.9_first-real-run.md) | First real run | manual | Done | run on 2026-10-29: real data, speakable replies in the user's language, personal data masked; the open findings are limits of the Go service or not scheduled | T-01.7, T-01.8 | 2026-10-28 |

## B. T-02 Model catalog refresh

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 14 | [T-02](T-02_model-catalog-refresh/T-02_model-catalog-refresh.md) | Model catalog refresh: no GitHub Models, Google free tier by default (epic) | epic | Done | all subtasks done; closed by the maintainer on 2026-10-30 (two exit criteria reworded in its closing note) | — | 2026-10-28 |
| 15 | [T-02.1](T-02_model-catalog-refresh/T-02.1_decisions.md) | Decisions | decision | Done | decided in PR-004 section 8 (2026-10-27) | — | 2026-10-27 |
| 16 | [T-02.2](T-02_model-catalog-refresh/T-02.2_profile-google-free.md) | Profile `google_free` | code | Done | verified with the suite | T-02.1 | 2026-10-28 |
| 17 | [T-02.3](T-02_model-catalog-refresh/T-02.3_confirm-ids.md) | Confirm the ids with the real key | manual | Done | run on 2026-10-28: 4 free-tier Google ids answered, `gemini-3.8-flash` 503, `gemini-2.5-*` 404; the paid-only Google ids dropped; the six Anthropic ids answered | T-02.1 | 2026-10-28 |
| 18 | [T-02.4](T-02_model-catalog-refresh/T-02.4_catalog.md) | Catalog | code | Done | the suite found and fixed one bug | T-02.1, T-02.3 | 2026-10-28 |
| 19 | [T-02.5](T-02_model-catalog-refresh/T-02.5_defaults-and-routing.md) | Defaults and routing | code | Done | verified with the suite | T-02.4 | 2026-10-28 |
| 20 | [T-02.6](T-02_model-catalog-refresh/T-02.6_prices-ratings-tokens.md) | Prices, ratings and token files | code | Done | verified with the suite | T-02.1, T-02.3, T-02.4 | 2026-10-28 |
| 21 | [T-02.7](T-02_model-catalog-refresh/T-02.7_tests-and-golden.md) | Tests and golden file | test | Done | golden regenerated; 890 passed, 3 known CRLF failures | T-02.4, T-02.5, T-02.6 | 2026-10-28 |
| 22 | [T-02.8](T-02_model-catalog-refresh/T-02.8_generated-documents.md) | Generated documents | docs | Done | regenerated; `proven` active | T-02.2, T-02.6, T-02.7 | 2026-10-28 |
| 23 | [T-02.9](T-02_model-catalog-refresh/T-02.9_documentation.md) | Documentation and ADR | docs | Done | ADR-012 written; PR-004 renamed | T-02.4 to T-02.8 | 2026-10-28 |
| 24 | [T-02.10](T-02_model-catalog-refresh/T-02.10_first-real-run.md) | First real run (on Claude since 2026-10-28) | manual | Done | the three messages ran on `claude_haiku` and `claude_mixed` (T-03.6); the Google runs stay in the notes | T-02.7, T-02.9 | 2026-10-28 |

## C. T-03 Claude as a provider

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 25 | [T-03](T-03_claude-provider/T-03_claude-provider.md) | Claude as a provider (epic) | epic | Done | all subtasks done; closed by the maintainer on 2026-10-30 | T-02 | 2026-10-28 |
| 26 | [T-03.1](T-03_claude-provider/T-03.1_decisions.md) | Decisions | decision | Done | in the conversation of 2026-10-28 | — | 2026-10-28 |
| 27 | [T-03.2](T-03_claude-provider/T-03.2_sanitizer-and-wiring.md) | The schema sanitizer and its wiring | code | Done | `anthropic_schema.py`, `vercel.py` | T-03.1 | 2026-10-28 |
| 28 | [T-03.3](T-03_claude-provider/T-03.3_tests.md) | Tests of the sanitizer and the wiring | test | Done | 23 tests | T-03.2 | 2026-10-28 |
| 29 | [T-03.4](T-03_claude-provider/T-03.4_profile-and-price-notes.md) | The profile, the Claude notes in the price file and the generated tables | code | Done | `claude_haiku`, not active | T-03.2 | 2026-10-28 |
| 30 | [T-03.5](T-03_claude-provider/T-03.5_documentation.md) | Documentation and ADR-013 | docs | Done | ADR-013 | T-03.2 to T-03.4 | 2026-10-28 |
| 31 | [T-03.6](T-03_claude-provider/T-03.6_first-real-run-on-claude.md) | First real run on Claude | manual | Done | all four kinds of message correct on Claude; six greetings on `claude_haiku` all right; closed 2026-10-30 | T-03.2 to T-03.5 | 2026-10-28 |
| 32 | [T-03.7](T-03_claude-provider/T-03.7_prices-of-the-other-claude-ids.md) | Prices of the other Claude ids | code | Done | the three ids priced from Anthropic's page of 2026-10-29 | T-03.4 | 2026-10-29 |

## D. T-04 A model out of capacity does not stop the message

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 33 | [T-04](T-04_llm-resilience/T-04_llm-resilience.md) | A model out of capacity does not stop the message (epic) | epic | Done | not provoked with a real 503 | T-02 | 2026-10-29 |
| 34 | [T-04.1](T-04_llm-resilience/T-04.1_decisions.md) | Decisions | decision | Done | taken by the assistant, the maintainer asked for the feature | — | 2026-10-29 |
| 35 | [T-04.2](T-04_llm-resilience/T-04.2_wait-and-fallback.md) | Wait, fallback models and the runner | code | Done | `failure.py`, `model_selection.py`, `phase_runner.py` | T-04.1 | 2026-10-29 |
| 36 | [T-04.3](T-04_llm-resilience/T-04.3_tests-and-documentation.md) | Tests and documentation | test | Done | 30 tests, ADR-014 | T-04.2 | 2026-10-29 |

## E. T-05 Structure: profiles, flows and steps (added 2026-11-02)

The order follows the stages of [PR-005](../proposals/PR-005-flows-steps-profiles.md) section 11; one pull request per stage (S1: T-05.2 and T-05.3; S2: T-05.4 to T-05.11; S3: T-05.12; S4: T-05.13; S5: T-05.14; S6: T-05.15; S7: T-05.16 and T-05.17).

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 37 | [T-05](T-05_profiles-flows-steps/T-05_profiles-flows-steps.md) | Structure: profiles, flows and steps (epic) | epic | In progress | T-05.1 to T-05.10 and T-05.12 done; S1 complete | — | 2026-11-02 |
| 38 | [T-05.1](T-05_profiles-flows-steps/T-05.1_decisions.md) | Decisions | decision | Done | Q05 to Q09, PR-005, ADR-015 | — | 2026-11-02 |
| 39 | [T-05.2](T-05_profiles-flows-steps/T-05.2_step-registry.md) | Step registry | code | Done | S1; 1003 passed, golden untouched | T-05.1 | 2026-11-02 |
| 40 | [T-05.3](T-05_profiles-flows-steps/T-05.3_folder-layout.md) | Folder layout | code | Done | S1; 1004 passed, golden untouched | T-05.2 | 2026-11-02 |
| 41 | [T-05.4](T-05_profiles-flows-steps/T-05.4_config-source.md) | Config source port and file loader | code | Done | S2; 1027 passed; a bad file goes to `errors`, not an exception | T-05.3 | 2026-11-02 |
| 42 | [T-05.5](T-05_profiles-flows-steps/T-05.5_model-sets-and-resolution.md) | Model sets, profile files and model resolution | code | Done | S2; 1034 passed; the model environment variables are gone | T-05.2, T-05.4 | 2026-11-02 |
| 43 | [T-05.6](T-05_profiles-flows-steps/T-05.6_assemble.md) | assemble() and its checks | code | Done | S2; 1099 passed | T-05.2, T-05.4, T-05.5 | 2026-11-02 |
| 44 | [T-05.7](T-05_profiles-flows-steps/T-05.7_profiles-of-todays-flows.md) | The profiles of today's flows | code | Done | S2; 1137 passed; the service stops routing and runs `default` until T-05.9 | T-05.5, T-05.6 | 2026-11-02 |
| 45 | [T-05.8](T-05_profiles-flows-steps/T-05.8_session-responses.md) | Session list of Response | code | Done | S2; 1161 passed; the prompts and the golden file are unchanged | T-05.3 | 2026-11-02 |
| 46 | [T-05.9](T-05_profiles-flows-steps/T-05.9_api.md) | API: profile, token, inputs, return, pause_id | code | Done | S2; 1212 passed; a request with none of the new fields gets today's answer | T-05.6, T-05.7, T-05.8 | 2026-11-02 |
| 47 | [T-05.10](T-05_profiles-flows-steps/T-05.10_tests-and-golden.md) | Tests and golden of the profiles | test | Done | S2; 1245 passed; the 14 old golden blocks are unchanged, five profile blocks added | T-05.7 to T-05.9 | 2026-11-02 |
| 48 | [T-05.11](T-05_profiles-flows-steps/T-05.11_first-real-run.md) | First real run: the `special` profile | manual | Todo | S2 acceptance; needs the Dynamics service up | T-05.10 | 2026-11-02 |
| 49 | [T-05.12](T-05_profiles-flows-steps/T-05.12_flows-as-json.md) | Flows as JSON | code | Done | S3; golden byte-identical; the files keep the old flow names | T-05.10 | 2026-11-02 |
| 50 | [T-05.13](T-05_profiles-flows-steps/T-05.13_tool-scoping.md) | Tool scoping | code | Todo | S4 | T-05.12 | 2026-11-02 |
| 51 | [T-05.14](T-05_profiles-flows-steps/T-05.14_prompts-per-profile.md) | Prompts per profile | code | Todo | S5 | T-05.12 | 2026-11-02 |
| 52 | [T-05.15](T-05_profiles-flows-steps/T-05.15_metrics-and-hash.md) | Metrics, profile hash and reserved data fields | code | Todo | S6 | T-05.12 | 2026-11-02 |
| 53 | [T-05.16](T-05_profiles-flows-steps/T-05.16_steps-as-json.md) | Steps as JSON declarations | code | Todo | S7, golden byte-identical | T-05.12 | 2026-11-02 |
| 54 | [T-05.17](T-05_profiles-flows-steps/T-05.17_commands-and-tables.md) | Commands and generated tables | code | Todo | S7 | T-05.15, T-05.16 | 2026-11-02 |
| 55 | [T-05.18](T-05_profiles-flows-steps/T-05.18_documentation.md) | Documentation and ADR-015 | docs | Todo | closes the epic | T-05.13 to T-05.17 | 2026-11-02 |

## F. T-06 Redesign (added 2026-11-02)

Starts only after T-05 is done and the maintainer has written the specification of T-06.1.

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 56 | [T-06](T-06_redesign/T-06_redesign.md) | Redesign: the new flows, steps, prompts and profiles (epic) | epic | Todo | waits for T-05 | T-05 | 2026-11-02 |
| 57 | [T-06.1](T-06_redesign/T-06.1_specification.md) | Specification of the new flows | decision | Awaiting user | the maintainer fills the table | T-05 | 2026-11-02 |
| 58 | [T-06.2](T-06_redesign/T-06.2_message-set.md) | The fixed set of messages | test | Todo | | T-05.17 | 2026-11-02 |
| 59 | [T-06.3](T-06_redesign/T-06.3_new-steps.md) | New steps | code | Todo | | T-06.1, T-05.16 | 2026-11-02 |
| 60 | [T-06.4](T-06_redesign/T-06.4_refine-prompts.md) | Refine the prompts, one step at a time | code | Todo | | T-06.1, T-06.2, T-05.14 | 2026-11-02 |
| 61 | [T-06.5](T-06_redesign/T-06.5_new-flows-and-profiles.md) | The new flows and profiles | code | Todo | | T-06.1, T-06.3, T-06.4 | 2026-11-02 |
| 62 | [T-06.6](T-06_redesign/T-06.6_real-run-and-comparison.md) | Real run and comparison | manual | Todo | | T-06.5 | 2026-11-02 |
| 63 | [T-06.7](T-06_redesign/T-06.7_documentation.md) | Documentation | docs | Todo | | T-06.6 | 2026-11-02 |
