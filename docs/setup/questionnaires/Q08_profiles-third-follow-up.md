# Q08 — Third follow-up (the last blockers before PR-005 can be written)

Vocabulary (yours): **agent = profile**, **workflow = flow**, **step** = one job. Same format as Q01 to Q07: write after `A:`; `UNKNOWN`, `NOT APPLICABLE`, `LATER` are valid; **never write secrets**. Each question has my **default**. **(!)** = it can change the design.

This file is short on purpose. After Q07 the model is clear; what is left are things your answers say in two ways, and one thing you asked for: *a plan that is very concrete and well defined* (Q07-4). To write that plan I need the points below.

---

## 0. What Q07 settled (tell me only if wrong)

- A request with no profile gets `default` (conversation + special), with no token (Q07-14 B). The robot is **not** one profile: it is several (Q07-1), and until Brain sends a profile its robot loses movement and gestures.
- Precedence of models: the most specific value replaces the broader one, the whole list is replaced; tools: the narrowest limit intersects. Model sets can be named at any level (Q07-10, Q07-11).
- Every step is converted to JSON (Q07-6 B), with **no new state fields made by non-coders**: the existing domain is the closed catalog; a developer adds fields.
- Files are loaded at start only; sources of the future: SQL, S3, LangChain services; every file has a `schema_version`; the Python steps stay in the repository (Q07-17).
- A wrong profile disables only that profile in production and fails the tests and `scripts/check_agent.py` (Q07-18 C); MCP tool names are checked against a snapshot (Q07-19 C); the layout of Q07-20 B (code under `application/`, JSON and prompts at the root); one cost table per profile (Q07-21 A); phase numbers stay as a label for now (Q07-9).
- The data policy (Q07-16) is **not built now**; the structure must leave room for it (I will reserve the fields: a step declares what kind of data it reads, a model declares what it may receive, and nothing enforces them yet).

---

## A. Who picks between the flows (the one thing I cannot guess)

1. **(!) The robot "will use multiple profiles", and a profile has one flow. Who picks the profile for each thing the user says?** Today Brain makes **one call per utterance** (ADR-003) and ai-agent decides inside (identification, then conversation, special, movement, and then a gesture). With several robot profiles one of these happens:
   - [ ] A: **Brain picks** the profile for each utterance (Brain must know whether it is a chat, a task or a movement); the session may use **a different profile on each message**
   - [ ] B: a **front-door profile** (`robot_triage`) only classifies and answers with the domain; Brain then calls the profile for that domain (two calls per utterance; ADR-003 changes)
   - [ ] C: ai-agent decides inside: a flow may hold a **branch** (after a step, continue with one of several sub-flows by a field the step wrote, for example `task_category.domain`); the robot profiles differ in other things (steps, tools, models, prompts), not in which kind of answer they give
   - [ ] D: other (describe how an utterance travels from Brain to the right flow)
   *Why it matters: A and B move the choice to the client and make a session change its profile (so the profile is **not** fixed per session, Q06-16). C keeps ADR-003 and Brain simple, and the flows of today (conversation, special, movement) become reusable parts of one bigger flow. Your answer in Q07-1 ("do not worry about how the robot will use it") says the robot side is not my concern, but the engine needs one of these rules.*
   *Default: C.*
   A:Brain will decide. The agent is just a passive way. The brain will asks a profile like robot-triage ,to generate the first separation, then depending on the aswear will go to one flow or another. That is made because there will be more than one of the selections and will be ebtter for reusability and managing.

2. **The `default` profile does "conversation + special" (Q07-14). Is the choice between them automatic?** A greeting is a plain reply; "create a document of this" needs a plan.
   - [ ] A: automatic, by the triage step, as today (this needs the branch of question 1 C)
   - [ ] B: not automatic: `default` is **one** list of steps that always plans and always writes (conversation and special become two different profiles, `default` and `chat`)
   - [ ] C: other
   *Default: A.*
   A:B

## B. The flows of the new design

3. **(!) Check this table (filled by the assistant from your Q08-1 and Q08-2).** In Q07-3 your lists do not match today's flows (for example `movement` lists triage, planner, worker, writer and editor, but no motion planner or validator; `conversation` lists a planner and a gate; `motion` and `emotion` are new names). I do not want to guess. Write **X** in each cell where the step is part of the flow. The column *Today* is what the code does now. If a flow is new, add a column.

   | Step | Today | `triage` | `chat` | `default` | `special` | `dynamics` | `movement` | `gesture` |
   |---|---|---|---|---|---|---|---|---|
   | 1 `triage_specialist` | every message first | X | | X | X | X | | |
   | 2 `project_manager` (plans actions) | special | | | X | X | X | | |
   | 3 `safety_quality_gatekeeper` | special | | | X | X | X | | |
   | 4 `cognitive_worker` (per action) | special | | | X | X | X | | |
   | 5 `mcp_operator` (per action, tool call) | special | | | X | X | X | | |
   | 6 `data_engineer` (cleans tool answers) | special | | | X | X | X | | |
   | 7 `draft_writer` | conversation, special | | X | X | X | X | | |
   | 8 `editor_in_chief` | conversation, special | | X | X | X | X | | |
   | 9 `answer_checker` | engine, on the next message of a paused run | hook | | hook | hook | hook | hook | |
   | 99 `user_clarification` | engine, when a step needs the user | hook | | hook | hook | hook | hook | |
   | 20 `motion_planner` | movement | | | | | | X | |
   | 21 `motion_validator` (plain code) | movement | | | | | | X | |
   | 30 `emotion_reader` | expression | | | | | | | X |
   | `gesture_builder` (plain code) | expression | | | | | | | X |

   *Tools:* `special` has **all** MCP servers; `dynamics` has **only** the Dynamics tools; `default` has the same tools as `special` (change it if `default` must have none). `chat`, `triage`, `movement` and `gesture` have none.

   *Filled by the assistant on 2026-10-30 from your answers Q08-1 (Brain asks a `robot-triage` profile first, then the profile of the answer) and Q08-2 (B: `default` always plans and writes, `chat` is the plain reply) and from today's flows; **you modify it**.* How I read it:
   - **`triage`** = today's identification flow alone (one step). It is the `robot-triage` profile of your Q08-1: it answers with the domain and Brain picks the next profile. It writes no reply.
   - **`chat`** = today's `conversation` flow (writer + editor). **`default`** = today's `special` with the triage at the front, because a client with no profile must get a complete answer in one call (Q07-14 B). **`special`** = the same steps without being the default (the profile Brain asks after the triage said "task"). **`dynamics`** = `special` with only the Dynamics tools; its triage is kept (Q07-3 said "all the steps 1 to 9").
   - **`movement`** = today's movement flow: planner + validator. Your Q07-3 listed triage, planner, worker, writer and editor for it; I did not follow that list because the planner of the movement is `motion_planner` (20), not `project_manager` (2). If you want the text steps in it, mark them.
   - **`gesture`** = today's expression flow (the emotion reader and the gesture builder). Your `motion` and `emotion` were two lists; in the code they are **one** flow, so I put both steps in one column. Split it if you want two profiles.
   - **9 and 99** are not steps of a flow today: the engine runs them when a step stops to ask the user (99) and when the next message answers that question (9). I marked them `hook` in every flow that has a step that can ask (triage, planner, gate, motion planner). In the new design they would be declared in the flow (`"on_pause": "user_clarification"`, `"on_resume": "answer_checker"`), so a flow with no asking step carries neither.

   **Two things this table makes visible (answer them, they change the design):**
   - **(!) The state between the two calls.** With Brain calling `triage` first and `chat` or `special` second, the second call starts with nothing: today the writer and the planner read `user_goal`, `task_category` and `constraints`, which the triage wrote in memory. Either (a) the session **keeps the result of the last triage** and passes it as the initial state of the next profile (the service remembers, Brain sends only the next message), (b) Brain **sends the triage answer back** in the second request (a new field), or (c) the second profile runs its **own light triage** (`chat` and `special` get a column X in row 1; one more model call, and the nothing-is-classified-twice rule goes). *Default: (a), it is how a session works today (`SessionService.sessions`).*
   - **Gestures:** today the router adds the gesture to the reply of `conversation` and `special`. Now Brain would ask `gesture` as another profile with the reply and the user message. Is that what you want? Or does the `chat` profile list the gesture steps at its end (one call, a longer flow)?
   - Do you want **new steps**? (for example the tool caller of Q07-4; a translator; a summarizer.) Name them and say where they go.
   A:Table filled by the assistant; answer here only what you change (the two bold points above and any cell).

4. **(!) Is redesigning the flows and the prompts part of this epic, or a separate one after the structure exists?** You wrote in Q07-4 that "all flows and steps will need refinement, the prompts also", and that the plan must be very concrete. Changing a flow or a prompt changes the answers the robot gives; moving everything to profiles, flows and JSON should not. If both go in one step, a bad answer has no obvious cause (the structure or the prompt?), and the golden file cannot tell.
   | Epic | What | Acceptance |
   |---|---|---|
   | **T-05 Structure** | layout, steps in JSON, flows, profiles, tokens, `assemble()`, API docs, metrics; the profiles `default` and the old ten reproduce **today's flows exactly** | the golden file does **not** change; the same requests go to the same models |
   | **T-06 Redesign** (after T-05) | the new flows of question 3, the new steps, the refined prompts, new profiles for the robot | a fixed set of messages run on real models (the real-run command), compared with T-05's answers; you review the prompts |
   - [ ] A: two epics as above (T-05 first, T-06 after; T-06 starts with your table of question 3)
   - [ ] B: one epic, both together (slower to verify; I will say which stage changes behaviour)
   - [ ] C: T-05 now and T-06 `LATER` (you write the new flows and prompts when you have them)
   *Default: A.*
   A:Default

5. **How will you judge that a refined prompt or a new flow is better?** Today the suite is mocks; the golden pins the exact request. A prompt that reads better can still make a model fail (Haiku's wrong greeting, T-03.6).
   - [ ] A: a **fixed set of messages** (a greeting, a question, a plan, a movement, a Dynamics question, a message in Spanish) with what a good answer must contain, run on a profile with one command and saved in `tests/output/`; you read the answers
   - [ ] B: the same, with an **automatic judge** (a model that scores the answer against the expected points); it adds cost and its own errors
   - [ ] C: by hand only
   *Default: A, as part of T-06.*
   A:Default

## C. State and steps in JSON

6. **Do I read "closed catalog of fields" right?** From Q07-6: a JSON step may read and write only fields that already exist in the domain (`user_goal`, `task_category`, `actions`, `constraints`, ...); a **developer** adds a field. So:
   - the **catalog of fields** is a developer-owned list (its name, its schema piece, its Python type in `domain/`), a data file the engine reads; the state holds exactly those fields
   - a step's **answer schema** is a *combination of existing schema pieces* (as `SCHEMAS` in the phase files does today: `user_goal`, `task_category`, ...), written in JSON; a non-coder cannot write a new piece
   - the typed `FlowState` stays as the real container (the catalog describes it; no generic bag), unless you want the bag
   - [ ] A: yes, as written
   - [ ] B: I want the generic bag (any key), and the catalog only for the steps that already exist
   - [ ] C: other
   *Why it matters: it changes what a non-coder can create: a step that combines the existing fields in a new order is a JSON file; a step that needs a new field needs a developer (your rule). A (not a bag) keeps the contract checks exact.*
   *Default: A.*
   A:Default

7. **What parts of a step stay in Python even when every step has a JSON file?** Today each step has `build_input` (what it reads, as a dict) and `apply` (what it writes back), and three steps are code (the executor of actions, the motion validator, the gesture builder). With the catalog of question 6:
   - the JSON declares: name, prompt (file or inline), answer schema (pieces), `reads` (fields), `writes` (fields), the model sets/lists it accepts, tools, kind (`llm`, `llm_per_action`, `code`)
   - Python stays only for `kind: code` and for the few steps where the input is not a plain dict of fields (the worker and the executor, which loop over the actions); each names its Python function in the JSON
   - [ ] A: yes
   - [ ] B: even those two become generic (a loop over a field is a JSON setting: `"for_each": "actions"`)
   *Default: B for the loop, A for the code steps; the executor is the first test of whether the JSON is expressive enough.*
   A:Default

## D. The token and the API while the contract is not changed

8. **What is the token for?** In Q07-13 you wrote that it is stored in the JSON because it is "only for verifying that the requested profile is the one really selected, not a security risk". In Q06-18 you wrote it was "an extra verification" for who may use the profile. These two are different:
   - [ ] A: the token is a **check against a mistake** (a client that sends the wrong profile name is told so); it is not access control; anyone with the repository can read it
   - [ ] B: the token is **access control** (only a client that has it may use the profile); then it cannot be plain in git, because anyone who reads the repository could use the `dynamics` profile, which reaches customer data (Q01-2: multiple users)
   *Whatever you answer, I recommend storing in the JSON the **hash** of the token (`"token_sha256"`), not the token: the client sends the plain token, the service hashes and compares; it costs nothing and the repository then holds no usable secret. With A it still checks mistakes; with B it is the minimum.*
   - [ ] a: as written in the JSON, plain (your Q07-13)
   - [ ] b: the hash in the JSON (my recommendation)
   - [ ] c: an environment variable (the earlier proposal)
   *Default: A with b.*
   A:Default

9. **How does ai-agent receive `profile` and the token before the `contracts` repository has the field (Q06-16, Q07 "update the API docs now")?** The request models come from the vendored wheel and do not know the field.
   - [ ] A: in **headers** (`X-Profile`, `Authorization: Bearer ...`) read by ai-agent itself; no contract change; later the contract can add the body field
   - [ ] B: in the **body**, with an extra request model written in ai-agent that adds the two fields to the contract's `StartRequest` (removed when the contract has them)
   - [ ] C: ai-agent implements nothing about the profile until the contract is released; only the docs and the engine
   *Default: A, because it needs nothing from another repository; `docs/api/api.md` documents the headers and the future body field.*
   A:B

10. **May one session use another profile on a later message?** Only needed if question 1 is A or B.
    - [ ] A: no, the profile of `/session/start` is fixed
    - [ ] B: yes; the history is shared; each message may carry its own profile and token
    *Default: A (question 1 C).*
    A:B

## E. Things only you can answer

11. **What would you hate to find out late?** (third time asked, in other words.) Pick or write:
    - [ ] the robot stops moving when Brain is not updated yet
    - [ ] the golden file changes without anyone noticing
    - [ ] a profile costs far more than expected
    - [ ] a profile reaches business data it should not
    - [ ] a non-coder's JSON mistake reaches production
    - [ ] the structure is so general that a simple change needs ten files
    - [ ] other:
    A:All og above

12. **The first real use at the end of T-05's first behaviour stage.** Describe one request from a client, from start to end, that you want to see working with real models (which profile, which message, what answer, what is logged). I will make it the acceptance test of that stage.
    A:for example a full special flow run.

---

**When you finish:** say "Q08 answered". Then I write the final PR-005: the model in one page, a table of every step with its JSON, the JSON of a flow and a profile as real examples of today's `default`, the stages with their acceptance tests, then ADR-015 and epic T-05 (and T-06 if you choose it); and mark Q05 to Q08 as processed in [00_README.md](00_README.md).
