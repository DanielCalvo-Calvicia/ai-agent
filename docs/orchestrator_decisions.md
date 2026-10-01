> **HISTORICAL (banner added 2026-10-01).** Decisions of 2026-09-21 (including the one real LLM run with `gemini-2.5-flash`). Paths and the single-flow design predate the flows split; the current design is in `README.md` and `CLAUDE.md`.

# Orchestrator decisions

Your answers to `docs/orchestrator_questionnaire.md`, how I read each one, and what is done. Written 2026-09-21. The priority you chose (Q21 A) is: make a simple case work correctly (findings A, B, C, D), then try it with a real LLM (Q19).

## Real LLM results (Q19)

**GitHub Models is retired**, so the default models cannot be used. The old URL `models.inference.ai.azure.com` no longer resolves, and `models.github.ai` answers `410 github_models_retirement_brownout`. `.env` has keys for Google and Groq. You chose Gemini (P1), and it is active.

Tried with `gemini-2.5-flash` for every phase (set only in the process environment, `.env` was not changed). The script is `tests/manual/real_flow_three_messages.py`.

| Message | What happened |
|---|---|
| "Hello, how are you?" | Triage said it needed the user ("no specific task"). 2 calls, 4 s. The reply was fine ("Hello! How can I help you today?") but small talk should not count as missing information. |
| "My family has 4 people. Make a table with each name." | Correct: it asked for the names. 2 calls, 3 s. It does not yet continue after you answer (pause and resume is not built). |
| "How many emails do I have?" | Triage refused ("I do not have access to your personal email accounts"). It does not know the tools. The MCP path was not reached with a real model. 2 calls, 18 s. |
| "Write a two-line poem about the sea, then translate it to Spanish." (an extra message, to reach the later phases) | **The whole chain worked.** 7 calls, 19.6 s, 9095 tokens. Action 2 received the poem of action 1 and translated it. The final reply had both. |

What the real calls showed:
- **Found and fixed:** the planner schema failed with a 400 (`reference to undefined schema ... subactions.items`). The `$defs` of the actions sat inside `properties.actions`, but `$ref: "#/$defs/action"` is resolved from the schema root. They are now moved to the root for every call that carries actions. A test checks that every `$ref` resolves.
- Gemini accepts the JSON schemas, the tool-free calls and returns bare JSON. Phases 1 to 4, 7 and 8 were seen working. **Phases 5 and 6 (MCP) were not tried with a real model.**
- **Latency:** triage alone took 3 to 14 s and up to 3700 tokens, because `gemini-2.5-flash` thinks before answering. A voice reply needs a faster setup (a lighter model, or thinking turned off) but you said to leave the models alone for now.
- **A real failure:** with the dead GitHub URL, the call was tried 3 times and the user got: "Sorry, I could not finish your request. What happened: I could not reach the language model service while understanding your request. Why: the network or the service is down. Please try again in a moment."

To use Gemini for now, put this in your environment (or `.env`):
```text
AI_AGENT_MODEL_PHASE_1=gemini-2.5-flash   (and the same for phases 2, 3, 4, 5, 6, 7, 8 and 99)
```

## Answers and status

| Q | Your answer | How I read it | Status |
|---|---|---|---|
| Q1 | B and C combined | The result is the reply text plus a structured part: the intent, the `next_step.status` and a list of actions for Brain. | Changed by P3: Brain does nothing, so the reply is the text, plus `status` (and maybe the intent). Not started. |
| Q2 | English for now. Later the last phase answers in the user's language. Length and tone: free. | No constraints for now, language English. Later, the final phase writes in the language of the user's message. | Not started (finding E). Free length is what happens today. |
| Q3 | Depends on `task_category.complexity`. If low it can pass. Otherwise the orchestrator makes subactions until each one is low. At most 10 subactions. | Decomposition is driven by complexity: an action that is not low is split until every leaf is low. | Subactions work now (limit 10). The complexity-driven loop is not built. Needs P2. |
| Q4 | A | Follow the schema: `requested_user_input`, `subactions`. | **Done.** |
| Q5 | A, maximum 10 subactions | Full recursion, at most 10 subactions per action. | **Done** (schema `maxItems: 10` and the mapper keeps the first 10). |
| Q6 | Not a priority. If needed, A. | Fill `server_id` with real server names and give the planner the tool names. | **Done.** |
| Q7 | Process all actions in order until done. An action that needs others gets their outputs. | A dependency-ordered executor for every action type. | **Done.** |
| Q8 | B | A failing tool is tried again. Then the failure is reported and the rest continues. | **Done** (the number of tries is the one setting, see P5; the error reaches the writer). |
| Q9 | A | The flow can pause right after triage. | **Done.** |
| Q10 | B, but resume where the step was waiting | Store the paused run in the session and continue from the waiting step. Nothing restarts. | Not started. Needs P4. |
| Q11 | A | Resume the paused plan with the new input. | Not started (same work as Q10). |
| Q12 | B, and also A | If the editor says it is incomplete, speak the answer and then ask what is missing. | Not started. |
| Q13 | Leave as it is | Same models and temperature. | Unchanged. But see the blocker: the default provider is gone. |
| Q14 | A | Only MCP results are cleaned. | **Done.** |
| Q15 | A | A bad or empty JSON answer is retried, then a spoken apology. | **Done** (see P5 and P6). |
| Q16 | B, 3 tries, then apology | `retry` or `error` status re-runs the phase up to 3 times, then apology. | **Done** for triage, planner, safety gate and editor. |
| Q17 | B, but 3 tries before asking the user | A `clarification` action is tried 3 times with the context before the user is asked. | Not started. |
| Q18 | A | Send JSON instead of Python text to the phases. Last. | Not started. |
| Q19 | B | Three real messages: small talk, one that needs a question back, one that needs MCP. | Done with Gemini, plus one extra message. MCP was not reached (see above). |
| Q20 | Five examples | Turned into tests once P4 is answered. | Partly (see P4). |
| Q21 | A | Findings A, B, C, D first. | **Done**, except the real call. |

## What changed in the code (findings A, B, C, D and parts of F, H)

- **A, B (names):** `requested_user_input` and `subactions` are used everywhere (schema, prompts, mapper, domain). The mapper now keeps nested subactions. Before, they were dropped.
- **C (MCP schema):** the empty `server_id` enum is gone. For each request the schema allows `""` or the real server names. Only `sse` servers are used, so the planner is no longer told about servers that cannot run (`fetch`, `filesystem`). The planner receives each server as its name and its tools (name, description, parameters), not the connection settings.
- **D (order):** phases 4, 5 and 6 became one dependency-ordered executor. An action runs when its subactions and dependencies are done and receives their outputs. It picks the cognitive worker or the MCP operator by type. Results are shared across types, so an MCP result can feed a cognitive action and the other way round.
  - Unknown or circular dependencies fail only those actions. If an input of an action failed, that action is skipped and says why. The final writer sees the failures.
  - Phase 6 runs only on MCP results (Q14 A).
- **H (MCP errors):** the tool call is tried twice. The `error` the LLM writes is now read and kept.
- **F (triage pause):** the flow can pause after triage.
- **Models:** `AI_AGENT_MODEL_PHASE_<n>` now accepts any model of the catalog (for example `gemini-2.5-flash`), not only GitHub ones.
- **Tests:** the golden file was recorded again on purpose (the prompts, the planner input and the action order changed). New tests cover the mapper, the schema, the servers, and each order rule. 129 pass.

## Your answers to P1 to P6

| P | Your answer | What I did |
|---|---|---|
| P1 | Use Gemini | Ran the real test with `gemini-2.5-flash` (results above). `AI_AGENT_MODEL_PHASE_<n>` now accepts any model of the catalog. |
| P2 | Yes; the limit is 10 subactions per action | Kept as the only limit. I will still add a small internal guard so a model that never says "low" cannot loop forever (I suggest 3 splitting rounds). Not built yet. |
| P3 | Brain does nothing. It asks the agent and receives the answer. | The agent returns text (Q1 B is dropped). Whether to add `status` and `intent` next to the text is open. |
| P4 | You did not understand | Asked again below, in plain words. |
| P5 | One setting | `AI_AGENT_MAX_ATTEMPTS` (default 3, the first try included). It controls: a failed LLM call, an MCP tool that gives no result, and a phase that answers "retry" or "error". |
| P6 | A custom apology that says what happened and why | Done. When something fails, the reply is a sentence like the one above: what happened, in which step, why, and what to do. It is built from a fixed text for each kind of failure (no LLM call, so it works even when the LLM is what failed) and never includes raw error text. `data.success` is `false` and `status` is `"error"`, so Brain can tell. |

Also done because of P5 and P6: an unknown session gets its own apology, and a failed call that cannot get better (a 400, 401, 403 or 404 from the provider) is not tried again.

## Your answers to the last three questions

1. **What the robot can do:** it can move each of its arms independently, by a number of degrees of rotation.
2. **Services:** none yet.
3. **A question and its answer:** if the user answers correctly, the flow continues. If not, the agent answers with a message, and keeps doing so until the user answers correctly or explicitly asks to stop and restart.

What I did with them:

- **Capabilities:** `prompts/capabilities.txt` says what the robot can and cannot do. Every phase sees it, in the system prompt, before its own instructions. Edit that file to change what the agent believes about the robot. I wrote that the robot can move its arms but the assistant has **no tool to order it yet**, because Brain does nothing with the agent's answer except speak it (P3). If you want the agent to handle "raise your left arm 30 degrees", tell me how the command should reach the robot.
- **Today's date and time** are in every phase (`CURRENT DATE AND TIME: Monday, 2026-01-05, 09:00 (UTC+01:00)`).
- **Small talk and refusals:** triage no longer asks the user for details on a greeting or a general question, or on something the robot cannot do (files, email, jumping...). The planner plans one "generation" step that answers, or says honestly that it cannot be done.
- **Pause and resume:** when a step needs the user (triage, planner or the safety gate), the run is saved in the session. The next message goes to a new small step, the answer checker (phase 9), which decides:
  - `answered` (or `confirmed`): the step that was waiting runs again with the answer, and the flow continues from there. Nothing before it runs again.
  - `not_answered`: the agent replies with a short message that says what is still needed, and keeps waiting. This repeats as long as the user does not answer.
  - `declined` (a "no" to a confirmation): the run is cancelled.
  - `stop` (an explicit request to stop, cancel, forget it or start over): the run is forgotten. The next message is a new request.
  - If the answer checker itself fails, the question stays waiting.
- **Confirmation** works the same way. After a "yes", the flow continues after the safety gate and the tools are no longer blocked.

## Real conversation with Gemini after these changes

| Message | Result |
|---|---|
| "Hello, how are you?" | Answered directly. 6 calls, 15 s. |
| "Which day is today?" | "Today is Monday." (it has the date now). 7 calls, 15 s. |
| "My family has 4 people. Make a table with each name." | Asked for the four names. |
| "What is the weather like?" (an unrelated reply) | The checker said it was not an answer: "I still need the names of your four family members. Could you please provide them?" 1 call. |
| "Ana, Luis, Pepe and Mia" | Continued, without asking again: checker, triage with the answer, planner, gate, worker, writer, editor. The table came back (but see the note below). |
| "Can you delete this file?" | "I cannot delete files, as I do not have the capability to interact with file systems." (after I fixed triage, see below) |
| "Can you jump?" | "No, I cannot jump." |
| "How many emails do I have?" | "I cannot access or count your emails ... However, I can talk with you, answer questions, write text ... and move each of my arms independently ..." |
| "Please raise your left arm 30 degrees." | "I can move my arms, but I cannot execute the command ... The capability to order arm movements is not yet connected from here." |

Two things the real run showed and I fixed in the prompts: triage still asked "Which file?" for the delete request (it now checks capabilities before deciding to ask), and the answer checker answered the user's off-topic question inside its message (it now says only what is still needed).

Still wrong or slow:
- **Speed:** every message takes 11 to 18 s (6 to 7 sequential calls with a model that thinks). Small talk is as slow as a real task. This is the fast path of Q3.
- **Tables:** the reply for the table had literal `\n` characters instead of line breaks. The model double-escaped the newlines when writing its JSON. Sending JSON instead of Python text to the phases (Q18) may fix it.
- The three answers of the checker cost one extra call per turn (about 1.5 s).

## Status of the plan

| Done | Not done |
|---|---|
| Names of fields, subactions, MCP schema and `$ref` fix, dependency order, retries with one setting, custom apologies, pause after triage, pause and resume with confirmation, capabilities, date, small-talk and refusal rules | Q3 complexity-driven splitting (P2), Q12 editor says incomplete, Q17 clarification actions tried 3 times, Q18 JSON inputs, Q2 answer in the user's language, Q1 `status` (and intent) next to the text, real MCP with a real model |

## Next steps (my proposal, in order)

1. **Speed (Q3).** If triage says complexity is `low` and the request needs no tool, answer with one call after triage instead of the whole chain. This needs your "yes": it changes the flow, and a wrong "low" gives a worse answer.
2. Complexity-driven splitting (P2): an action that is not `low` is split until it is (at most 10 subactions, and 3 splitting rounds as a guard).
3. JSON inputs for the phases (Q18), and check the `\n` problem again.
4. Q12 (editor says incomplete), Q17, Q2 (reply in the user's language), Q1 (status next to the text).
5. Try phases 5 and 6 with a real model when there is a real tool.
