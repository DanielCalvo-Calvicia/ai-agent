# Q09 — A profile on every message: what that changes (last round before PR-005)

Vocabulary (yours): **agent = profile**, **workflow = flow**, **step** = one job. Same format as Q01 to Q08: write after `A:`; `UNKNOWN`, `NOT APPLICABLE`, `LATER` are valid; **never write secrets**. Each question has my **default**. **(!)** = it can change the design.

Your Q08 answers made one decision that reaches further than the others: **Brain calls a profile for every message** (first `robot-triage`, then the profile of the answer; Q08-1, Q08-9 B, Q08-10 B). That makes the service a set of small, separate calls that Brain chains, instead of one call that does everything. It is a good design for reuse, and it opens the questions below. I will not ask about anything that has a good default and no consequence.

---

## 0. What Q08 settled (tell me only if wrong)

- **Brain chooses the profile for each message** and may use a different one on each message of the same session; history is shared (Q08-1, Q08-10 B). `/session/start` therefore does **not** need a profile; the profile and the token travel with **every** `/session/message`, in the **body**, through an extra request model written in ai-agent until the `contracts` repository has the fields (Q08-9 B). The token is never written to a log.
- `default` always plans and writes (a client with no profile gets it, with no token); `chat` is the plain reply; `triage` is only the classification; `special`, `dynamics`, `movement`, `gesture` as in the table of Q08-3, which you accepted without changes.
- Two epics: **T-05 Structure** (golden file unchanged) and **T-06 Redesign** (new flows, new steps, refined prompts) after it; a fixed set of messages judges prompts (Q08-4, Q08-5).
- A closed catalog of state fields (typed `FlowState` stays); Python only for code steps; a loop over actions as a JSON setting (Q08-6, Q08-7).
- The token is a check against a mistake, stored as a **hash** in the JSON (Q08-8: `A with b`).
- Your Q08-11 answer is "all of the above": I will write the PR with a risk table that says how each one is handled.

---

## A. The calls Brain chains

1. **(!) The second call starts with nothing. How does the second profile get what the triage found?** Today the writer, the planner and the gate read `user_goal`, `task_category` and `constraints`, which the triage wrote in memory in the same call. Now `triage` is one call and `chat` or `special` is another (and `gesture` a third, which needs the reply and the user's message). You did not choose in Q08-3. Options:
   - [ ] A: the **session keeps the last triage** and the next profile starts from it (consumed once; Brain sends only the message)
   - [ ] B: Brain sends **`inputs`**: an object in the request with the fields the profile needs (`{"triage": {...}}`, or `{"reply": "...", "user_message": "..."}` for `gesture`); each profile declares which inputs it accepts and requires, and the startup check refuses a profile whose first steps read something no input or step provides
   - [ ] C: each profile runs its **own light triage** (one more model call in `chat` and `special`; the rule "nothing is classified twice" goes)
   *Why it matters: A hides state in the service (what if Brain calls `chat` twice, or two requests of one session run at the same time?) and cannot feed `gesture`. B is explicit, can be tested with a fixed request, makes any chain of profiles possible (not only triage then answer) and is the "plug and play" you asked for; its cost is one more field in the contract. C is the simplest and the most expensive.*
   *Default: B.*
   A:B (confirmed and corrected by the maintainer in chat, 2026-11-02; written by the assistant). The steps of a flow share their results **inside the flow** (the state); the client never sees or carries that state. The client knows only **what it sends** and **the result of the flow**. So:
   - The **result of a flow is the `Response` object of its last step**, whole (maintainer's choice B). That object is what the service returns to the client **when the client asks for it** (`output`, question 2) and what the client sends back, unchanged, in the optional `inputs` of the next request. **The client chooses, on each request, how much it gets back** (maintainer, chat 2026-11-02): only the output text of the last step (a frontend needs just that string) or the whole `Response` (Brain, to chain `identification` with the next profile). The text is always returned; the whole object only on request. Brain copies one into the other and does not open it.
   - A profile that runs **one step** is allowed and expected: `identification` (the profile that runs only the triage step; the name replaces `triage` in this file and in the table of Q08-3), and likewise any step may get its own profile. The client asks for a **profile**, never for a step by name: tokens, tools and models stay per profile.
   - The profile **declares** which inputs it accepts and which it requires (for `chat`, `special`, `default` and `dynamics`: the fields of the identification result, `intent`, `user_goal`, `task_category`, `constraints`, `missing_information`). For `gesture` the input is the reply text and the user's message.
   - Rules: (1) a missing required input is answered with a clear error before any model call; (2) the startup check refuses a profile whose first step reads something that no input and no earlier step provides; (3) `inputs` is read with the same schemas as an LLM answer (the existing catalog of fields, Q08-6), so it cannot carry a field that does not exist; (4) its content is data from the client, never instructions; (5) assistant's addition, change it if you disagree: the metering fields of the `Response` (`tokens_usage`, `raw`) are **not** returned to the client and are ignored if the client sends them, because they describe the cost of one internal call and `raw` may hold the model's unfiltered text.

2. **What does a profile answer with?** Today the answer is `response` (text), `directives` (movements), `awaiting_user_input` and `flow`. A `triage` answers with a classification and no text; Brain must read it to choose the next profile. In Q07-5 you said the output is "the proper output of the last step".
   - [ ] A: add to the answer an `output` object (**the `Response` object of the flow's last step**, as decided in question 1: for `identification` the intent, user goal, task category, constraints and missing information; for `chat` nothing more than `response`) and a `profile` field (the one that ran); `response` and `directives` stay as they are; **`output` is present only when the request asks for it** with a new optional field (proposed name: `return`, values `"text"` (default: only `response`, as today) and `"full"` (`response` plus `output`)); a client that sends nothing gets exactly today's answer
   - [ ] B: other (write what Brain needs to read from a `triage` answer)
   - Which values does Brain map to which profile? Write the **domains** (or labels) the `triage` may return, and the profile each goes to (`communication` -> `chat`, `movement` -> `movement`, anything else -> `special`, ...). I will put the table in `docs/api/api.md` so Brain's side is written down, even if you build it later.
   *Default: A, and the mapping of today's `FLOW_BY_DOMAIN` as the first table.*
   A:A, with the profile default (accepted by the maintainer in chat, 2026-11-02; written by the assistant).
   - **Request** gains `profile`, `token`, `inputs` (question 1), `return` (`"text"` or `"full"`) and `pause_id` (question 3). A client that sends none of them gets exactly today's answer.
   - **Answer** keeps `response` (the output text of the last step, always present, empty for a profile that produces no text), `directives`, `awaiting_user_input` and `flow`, and gains `profile` (the profile that ran), `pause_id` (only when `awaiting_user_input` is true, question 3), `discarded_pause` (only when a paused run was discarded, question 3) and `output` (the `Response` of the last step; present only when the request asked for `"full"`). `tokens_usage` and `raw` are never part of `output` (question 1, rule 5).
   - **A profile may declare `"default_return"`** (`"text"` unless it says otherwise). `identification` declares `"full"`, because it produces no text and Brain needs its result to chain. The client may override it on each request; the client always has the last word.
   - **The mapping from domain to profile is Brain's rule**, written in `docs/api/api.md` (the service no longer routes, question 7). First table, from today's `FLOW_BY_DOMAIN`: `communication` -> `chat`; `movement` -> `movement`; anything else -> `special` (`dynamics` for Business Central questions). `gesture` is asked with the `reply` and the user's message as `inputs`, never with the identification result.
   - The contract change itself (the fields in the `contracts` repository) is yours, later (Q06-16); until then ai-agent reads the new fields through its own extended request model (Q08-9 B).

3. **(!) A profile asked the user a question. Which profile receives the answer?** `awaiting_user_input` is true: a step stopped to ask (the planner needs a detail, the gate needs a confirmation, the triage cannot classify). The user answers "yes, go on". If Brain runs the triage first for every utterance, that "yes" is classified as a chat message and the question is lost.
   - [ ] A: Brain sends the answer **to the same profile** that asked; the service checks it: another profile while a run is paused answers `PROFILE_MISMATCH` (a clear error) and the run stays paused
   - [ ] B: the service resumes the paused run **whatever profile is sent** (the profile of the request is only checked for its token)
   - [ ] C: a new utterance always **cancels** the paused run and starts over
   *Default: A. Brain already knows (`awaiting_user_input`), and a mismatch is a bug in Brain that should not pass silently.*
   A:A, improved by the maintainer with a token (chat, 2026-11-02; written by the assistant). The service issues a **`pause_id`** when a run pauses; Brain sends it back with the answer. It binds the answer to the exact question, so a retry cannot run the step twice and an old answer cannot reach a newer question. It is not a secret and not authentication: it is separate from the profile `token` (Q08-8) and may be logged.
   - **The answer** of a request that pauses carries `awaiting_user_input: true` and the new field `pause_id` (it joins the new fields of question 2).
   - **The request** gains an optional field `pause_id`.
   - **Rules:**
     | Request | Result |
     |---|---|
     | `pause_id` present, same profile, run still paused | it is the answer: phase 9 (`answer_checker`) judges it (answered, confirmed, declined, stop, not an answer) and the same step reruns with the clarification, as today; the `pause_id` is consumed |
     | `pause_id` present, another profile | `PROFILE_MISMATCH`; the run stays paused and keeps its `pause_id` |
     | `pause_id` unknown or already used | `PAUSE_NOT_FOUND`; Brain treats it as a new message (like `SESSION_NOT_FOUND`, a retry of the same request without it) |
     | no `pause_id` while a run is paused in the session | a **new message**: the paused run is discarded and logged; the answer carries `discarded_pause: true` so Brain can notice a forgotten `pause_id` |
   - On a resume, `inputs` is ignored (the paused state is in the service) and the profile `token` is still checked.
   - **Limits:** one paused run per session (a new pause replaces the previous one); lost on restart, because sessions live in memory (ADR-009), and the answer is then `PAUSE_NOT_FOUND`; no time limit for now.
   - **Leaving a question:** a new message without `pause_id` is how the user abandons it. This replaces the cancel offered in the explanation; "stop" still works through phase 9.

4. **Which calls write to the shared history?** With several calls per utterance, a naive "every call adds the user message and the reply" gives: user message twice (`triage` and `chat`), a `triage` with no reply, a `gesture` call whose "message" is the robot's own reply.
   - [ ] A: only a call that **produces a reply** (`response` not empty) adds one turn (the user's message and the reply); `triage`, `gesture` and a movement that is not announced add nothing
   - [ ] B: each profile declares `"history": "write" | "read" | "none"`, and the default is A's rule
   - [ ] C: Brain sends the history it wants in `inputs` (the service keeps none; this ends sessions)
   *Default: B.*
   A:The maintainer's own model, none of the three options (chat, 2026-11-02; written by the assistant). The session keeps a **list of `Response` objects, one per request**. The `user_goal` of each `Response` holds the **input and the output** of that request, so no call needs a rule about writing to the history and no text pairs are saved separately (this replaces `user_session.remember(message, reply)` of `session_service.py`).
   - Each request appends its `Response`. The history a step reads is the **last N entries** (`AI_AGENT_HISTORY_TURNS`, 6 by default); a prompt takes the input and the output of each entry from its `user_goal`.
   - The per-profile `"history": "write" | "read" | "none"` of the proposal is **dropped**.
   - Two implementation checks, not questions: (1) `Response.user_goal` is optional in the code today, so `assemble()` must check at startup that the final result of every profile carries a `user_goal` with its input and its output; (2) a profile that ends in a code step with no `Response` (`gesture`, which ends in `gesture_builder`) adds no entry.
   - The same `Response` objects are what a client may send back in `inputs` (question 1); the history is the session's own copy and is never taken from `inputs`.

## B. What `default` and `special` may reach

5. **(!) `special` has all the MCP servers and `default` has the same (Q08-3). `default` is what a client gets with no profile and no token. Is that right?** It means any client that sends nothing can ask for customers' orders through the Dynamics tools, which reach customer data (Q01-2: several users; and in Q08-11 you said you would hate "a profile reaches business data it should not").
   - [ ] A: `default` and `special` have **no** Dynamics tools (nor any MCP that reaches business data); only `dynamics` has them, and `dynamics` requires its token
   - [ ] B: `special` has all the servers (it needs its token); `default` has none
   - [ ] C: as in the table (both have all the servers)
   *Default: A. It also fits the data policy of Q07-16 that comes later: the one profile that reaches business data is named `dynamics`, so the policy has one place to apply.*
   A:B

6. **`default` always plans: the cost of a greeting.** With Q08-2 B a greeting sent with no profile goes through the triage, the planner, the gate and the writer and editor (about six model calls) where today it takes three (triage, writer, editor). Brain avoids it by asking `triage` first and then `chat`; a client with no profile (a web chat, a test) pays it.
   - [ ] A: accepted; that client should choose `chat` or the triage-then-profile chain too
   - [ ] B: `default` skips the planner and the gate when the triage says it is a plain message (this needs the branch inside a flow that you decided against in Q08-1/2)
   *Default: A. The cost is written in the generated cost table of `default` (Q07-21 A).*
   A:Default. The user that selects default and not chat is their problem. if they want a conversation they must use chat

7. **What exactly does T-05 reproduce?** You accepted that T-05 does not change the golden file. Today there are five flows (identification, conversation, special, movement, expression) and one router. In the new design the five become the profiles `triage`, `chat`, `special` (all tools), `movement` and `gesture`, each **identical** to its flow of today, and the router (the logic that chains them) moves to Brain. `default` and `dynamics` are new combinations of existing steps.
   - [ ] A: yes: the golden file has one block per profile `triage`, `chat`, `special`, `movement`, `gesture` and they match today's requests byte for byte; `default` and `dynamics` are tested with mocks, with no golden (Q05-19 said one golden for the default; it becomes one per flow, because that is where a request is pinned)
   - [ ] B: other
   *Default: A. Until Brain chains the profiles, the service **no longer routes**: a client that sends `chat` gets chat; there is no automatic choice inside the service anymore (your Q08-1).*
   A:Default

## C. Names and the first real use

8. **Do clients share profiles?** Without `extends` (Q06-8 B) a profile is a full file. If the web chat wants the robot's `chat` but with other tools or models, it is a copy.
   - [ ] A: **generic** profiles (`triage`, `chat`, `special`, `movement`, `gesture`, `dynamics`, `default`) shared by every client, with one token each; a client-specific profile (`robot_chat`) is written only when it differs; the field `client` of `/session/message` tells the metrics who called
   - [ ] B: each client has its **own profiles from the start** (`robot_triage`, `robot_chat`, `web_chat`, ...), with their own tokens; no profile is shared
   *Why it matters: with a shared token every client of `chat` has the same one, so the token cannot tell clients apart (fine if it is only a check against a mistake, Q08-8). With B you get a token per client and many copies of the same JSON.*
   *Default: A. In Q08-1 you wrote `robot-triage`; I read it as "the triage profile Brain uses", not as a profile that only the robot may use. Tell me if it is the second.*
   A:A. but robot-triage is an specific profile, separated from robot and default. This is done inc ase some prompts need refinement per profile_step ,that differs from the eneric ones.

9. **(!) The first acceptance run (Q08-12: "a full special flow run").** Make it concrete, so I can write it as the test of the first stage that changes behaviour:
   - Which profile? (I propose `special`, then `dynamics` as the second run.)
   - Which message? (for example "Dime el estado de los pedidos del cliente <a test customer code>"; use a **sandbox** code or a made-up one, never a real customer)
   - Which models? (a set of Q01-6, Claude: `claude_mixed`, or another)
   - Which tools? Is the Dynamics service running that day? It refuses the connection from this very session; the run needs it, or it is the planner's answer without the tool.
   - What must be in the logs and the metrics at the end: profile, flow, step, model, tokens, cost, the hash of the assembled profile (Q07-27)?
   A:special. "Dime el estado de los pedidos del cliente CL-1001". claude_mixed. Dynamics. Not needed

10. **Anything that does not fit in a question.** Is there still something you think I misunderstood, or that the PR must say in a different way? (A sentence is enough.)
    A:

---

**When you finish:** say "Q09 answered". Then I write the final PR-005 (the model in one page; a table of every step with its JSON; a real flow and a real profile as JSON; the request and answer of the API with the new fields; the stages with their acceptance tests; the risk table of Q08-11), open ADR-015 and epics T-05 and T-06, and mark Q05 to Q09 as processed in [00_README.md](00_README.md).
