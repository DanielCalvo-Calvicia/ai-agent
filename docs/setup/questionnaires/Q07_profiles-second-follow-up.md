# Q07 — Second follow-up (the points where your Q06 answers pull in different directions)

Vocabulary used from here on (yours, from Q06-5): **agent = profile** (what a client picks), **workflow = flow** (an ordered list of steps), **step** = one job. I write "profile" and "flow" below; "agent" and "workflow" mean the same.

Same format as Q01 to Q06: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets** (write *where* they live). Each question has my **default**. **(!)** = it can change the design. Fewer questions than before: each one is a point where two of your answers do not fit together yet, or one that your answers opened.

---

## 0. What Q06 settled (no answer needed, tell me only if wrong)

- A profile has **one flow, or one ordered list of steps**; never several flows with a router outside the flow (Q06-1, Q06-2).
- A profile is chosen by the client at `/session/start` and is fixed for that session; the files never change at run time; to change them you edit and redeploy (Q06-16, Q06-21).
- Profiles do **not** extend each other; shared model tables are **model sets** (Q06-8). The ten old tables become generic profiles, each tested by the developer before it is kept (Q06-9).
- Tools: the **narrowest limit wins** (profile ∩ flow ∩ step); a tool outside is neither shown nor callable; a profile may name a whole server or single tools (Q06-10 to Q06-12).
- Prompts: a profile may replace or add to a step's prompt, in a file or written inline (Q06-13, Q06-14). The reply language follows the user (Q06-15).
- The API: the `profile` field goes in `/session/start`; this change documents the API now and the `contracts` repository is changed later by you (Q06-16).
- Every profile needs a **token**; unknown profiles are never listed (Q06-18, Q06-20).
- The folder layout of Q06-28 option A, as the first stage; the stage order of Q06-29 option A.
- The structure must let prompts, profiles and flows come from **other sources** later (Q06-30).

---

## A. The flow: branching, conditions and what a flow may contain

1. **(!) The robot has three kinds of answer (a chat reply, a task with tools, a movement) and a profile has only one flow. How does one flow pick between them?** In Q05-4 you listed `robot` as conversation + special + motion. If a profile can have only one flow, that flow must *contain* the choice. Three ways:
   - [ ] A: a flow may hold a **switch**: after a step, "go to the sub-flow named by this field" (`{"switch": "task_category.domain", "cases": {"movement": "movement", "communication": "conversation", "*": "special"}}`); the sub-flows are flows themselves, reusable
   - [ ] B: a flow is a flat list of steps with a **`when`** on each (`{"step": "motion_planner", "when": "task_category.domain == 'movement'"}`); no sub-flows
   - [ ] C: the `robot` profile is not one flow: it is one **router profile** that names several flows (what I assumed in Q06-1), and the "only one flow" rule is for the other profiles
   *Why it matters: A keeps the three existing flows as small reusable pieces and a profile like `dynamics` just uses `special`. B has no sub-flows and repeats steps. C breaks your rule on purpose. With A the flows of today (`conversation`, `special`, `movement`) become reusable **sub-flows**, and the "redo and reorganize the flows" you wrote is mostly that.*
   *Default: A.*
   A:The tobot client will use different flows. It will change to adapt the current architecture of the ai-agent. The new robot will use multiple different profiles, so dont worry about how to robot will use the ai-agent.

2. **Which conditions may a flow write, and who writes the code behind them?** A flow written in JSON by someone who does not code can say "pause and ask the user if the step says it needs input", "retry if the answer says retry", "only if the reply is not empty". Today those are small Python functions (`pause_if`, `retry_on_status`, `jump_after`).
   - [ ] A: a **fixed list of named conditions** written by a developer (`needs_user_input`, `has_reply`, `retry_requested`, ...); a flow can only use those names
   - [ ] B: a small **expression** language written in the JSON (`state.reply != ''`, `state.domain == 'movement'`)
   - [ ] C: both
   *Why it matters: B is flexible and is also a language to design, test and secure. A is a short list now and grows as you need it.*
   *Default: A.*
   A:Default

3. **(!) Describe the flows you want in the new design, one line each.** You said the flows "are mixed and will be redone". Your example in Q06-4: a flow that asks an MCP tool and then runs the draft writer and the editor, with no triage and no planner. Please list the flows you want to exist after the reorganisation, with the steps in order (names of today's steps, or "new step: ..."):
   - `conversation`: ?
   - `special` (plan, gate, execute, write, edit): ?
   - `movement`: ?
   - the Dynamics one from your example: ?
   - the gesture (`expression`): a flow, a trailing step of a flow, or a step list a profile adds at the end?
   - any other:
   *Why it matters: it is the most useful answer in this file. The flows you write here are the first test of the design.*
   A:
   - conversation: triage_specialist, project_manager, safety_quality_gatekeeper, cognitive_worker, drawft_writter, editor_in_chief
   - special: all the steps from 1 to 9, with all the mcps
   - movement: triage_specialist, project_manager, cognitive_worker, drawft_writter, editor_in_chief
   - dynamics: all the steps from 1 to 9 ,with only the mcp tools from dynamics
   - motion: the related actual steps for gesture
   - emotion: the steps that requires emotion.

4. **(!) A flow with no planner that "asks an MCP and then writes": who decides which tool to call and with what?** Today the MCP operator (phase 5) runs **per planned action**: the planner writes the action (tool, inputs) and the operator carries it out. With no planner there is no action to run. Options:
   - [ ] A: a **new step** (for example `tool_caller`) that reads the user's message, chooses the tool (inside the allowed list) and calls it, and writes the result for the draft writer; I design it as a normal step
   - [ ] B: the MCP operator is changed to work without a planned action (it reads the user message)
   - [ ] C: this flow keeps a planner (a smaller one); only the safety gate and the editor are dropped
   *Default: A.*
   A:All flows and steps will need refinement, this modifications are huge, because the prompt also needs refinements, that is why this plan needs to be very concrete and well defined

5. **May a step write to the reply directly, and what is "the answer"?** The startup rule of Q06-6 (ii) needs to know which step produces the text that goes back. Today `FlowState.final_text()` reads the editor's field, else the draft's, else something else.
   - [ ] A: each flow declares `"reply_from": "editor_in_chief.final_text"` (or another field); the check reads that
   - [ ] B: a fixed convention, the last step that writes `reply`
   *Default: A.*
   A:The return can be the proper output of a step, all depends on what is the final step

## B. Steps, the state and "everything is JSON"

6. **(!) How far does "the configuration of each step will be done via JSON" go?** In Q06-7 you chose the declarative step (a step defined fully in JSON). Today a step is Python (`build_input`, `apply`) plus a prompt, plus a schema in `full.schema.json` (generated into a tree) plus `domain/` objects, and it reads and writes **typed fields** of `FlowState` (`user_goal`, `task_category`, `actions`, ...).
   - [ ] A: **only new steps** are JSON; the 12 existing steps stay in Python and only get a small JSON declaration (name, prompt, reads, writes, model needs); the typed `FlowState` stays, and JSON steps use a generic `values` bag next to it
   - [ ] B: **all steps** are converted to JSON (prompt, schema, inputs, where to write); the typed `FlowState` is replaced by a generic bag; Python remains only for the steps that call code (the executor, the validator, the gesture builder)
   - [ ] C: like A now, B as a later goal
   *Why it matters: B is the cleanest end state and the largest change: the schema tree, the `domain/` objects, the golden file and 12 prompts' inputs all move. A leaves two kinds of step next to each other for a long time.*
   *Default: C.*
   A:B. The current domain will work, i dont think that will need more domain for now. The new steps will use the same values. In case of creating new the developer will create them. For a non-code user they cant create fields that arent existing.

7. **How does a declarative step get its input and say where its output goes?** For a JSON step I suggest: `reads` lists fields of the state (the engine sends them as the user message of the call, like `_build_input` does today); the answer schema is a JSON file; `writes` names the key where the whole answer is stored (or a map from answer fields to state keys).
   - [ ] A: yes, as written
   - [ ] B: the step also needs a **template** for the input (`"input_template": "Translate: {reply}"`) because a dict of fields is not what a non-coder writes
   - [ ] C: other (write it)
   *Default: A, B as an extra if you need it.*
   A:Default

8. **What if the JSON schema a non-coder writes does not work on a provider?** Claude's endpoint accepts a strict, sanitized schema of at most three nesting levels (ADR-013); Google and the others have other limits. A non-coder will not know that.
   - [ ] A: the startup check runs each custom schema through the **provider rules of every model the step may use** (its profile, its fallbacks) and refuses it with a message that says which rule broke
   - [ ] B: only an error at run time
   *Default: A.*
   A:Default

9. **Do the numeric phase ids stay?** With no environment variables to override models (Q05-17) the ids (`PHASE_ID`, `AI_AGENT_MODEL_PHASE_<n>`) are used only by metrics, logs, Langfuse and the generated docs.
   - [ ] A: retire them; the step **name** is the key everywhere; the generated tables and the golden are rebuilt once
   - [ ] B: keep them only as a label in metrics, for continuity with the cost tables already recorded (`measured_runs.json`)
   *Default: B until the history in `measured_runs.json` is not needed, then A.*
   A:Default

## C. Models, fallbacks and precedence

10. **(!) What is the exact order when profile, flow and step all name a model?** In Q06-23 you wrote: "the profile sets a model, then the flows and the steps use that; from up to down". In Q06-23 you also said the profile, the flow and the step may each carry a list. I read it as a **default that goes down and is replaced by a more specific value**, so the most specific wins. Example for step `draft_writer` in flow `conversation` in profile `robot`:
    ```text
    robot.flows.conversation.steps.draft_writer.models   <- most specific, wins
    robot.flows.conversation.models                      <- the flow's own list for all its steps
    robot.models                                         <- the profile's list for everything
    step definition: models                              <- the step's own default (today DEFAULT_MODEL), last
    ```
    - [ ] A: yes, the most specific value replaces the broader one, and the **whole list is replaced** (a step's list does not add to the flow's list)
    - [ ] B: yes, but the lists are joined (step, flow, profile, no repeats)
    - [ ] C: different: write the order you want
    *The tools (Q06-10) are the opposite on purpose: the narrowest limit **intersects**; models **override**. Confirm both.*
    *Why it matters: if a flow file sets models, one flow reused by two profiles carries the same models in both; a profile then needs a way to override a flow's models (the first line above).*
    *Default: A.*
    A:Default

11. **Where do the model sets (Q06-8) sit in that order?** A profile names a set: `"models": "claude_mixed"`.
    - [ ] A: a set is the profile's list level (line 3 above) and may be overridden by the profile's own flows and steps entries
    - [ ] B: a set may be used at any level (a flow or a step may also name a set)
    *Default: B.*
    A:Default

12. **(!) The ten old tables as "generic profiles" (Q06-9).** A profile today needs a flow, and the old tables have none. To make them profiles I would pair each with the `default` flow (the one that replaces conversation + special).
    - [ ] A: yes; each old table becomes a **model set** *and* a generic profile of the same name that uses the `default` flow; you test and keep or delete each one
    - [ ] B: only the model sets are kept; the generic profiles are written when a client needs one
    - Which of the ten do you already know you will not use? (My list of "Untested and unreferenced": `budget`, `balanced`, `quality`, `budget50`, `budget50_groq`, `claude_sonnet`, `google_free`.)
    *Default: A, and I leave the unused ones in a folder `profiles/_unverified/` that the service does not load.*
    A:Default

## D. Safety: tokens, data and the client

13. **(!) How does the token of a profile work?** You said "there will be a token for each profile". I read it as: the client sends the profile name **and** the token at `/session/start`, the service compares it with the one of that profile, and the session is bound to the profile.
    - **Where is a token stored?** Not in the JSON file (it would be in git). Proposal: the profile names an environment variable (`"token_env": "AI_AGENT_TOKEN_ROBOT"`); the value lives in the deployment's secret store.
    - **How is it sent?** A header (`Authorization: Bearer ...`) or a body field? Proposal: header, because the contract field would be logged with the body.
    - **Once per session?** Only at `/session/start` (the `session_id` then proves it) or on every message?
    - **One token per profile, shared by all clients of it?** (Every robot with the same token.) Or one per client?
    - [ ] A: as proposed (env var, header, once per session, one per profile)
    - [ ] B: change it (write the differences)
    *Default: A. The tokens are compared in constant time and never written to a log.*
    A:For now will be on the json, there is no problem to leave it there because it only for verifying that the requested profile is the one that it was really selected, like a validation for internal verification, not a security risk

14. **(!) What does a client that sends no profile get?** In Q06-17 you chose C, but your note says the robot has its own profile separate from `default`. Those two do not fit: under C `default` would also be the robot. I need a rule for Brain, which sends nothing today and uses movement and gestures.
    - [ ] A: no profile = an error; Brain must send `robot` and its token before it works again (nothing is in production, Q05-22)
    - [ ] B: no profile = the profile called `default` (conversation + special, **no movement**), without a token; Brain's robot loses movement until it sends `robot`
    - [ ] C: no profile = `default`, but until Brain is updated I make `default` the same as `robot` (movement and gestures), and I separate them when Brain sends a profile
    *Default: A. It is the only one where nothing silently changes behaviour or skips the token.*
    A:B,  a defaulr ptofile will do conversation + special, the robot one will be separated into multiple flows.

15. **A wrong token and an unknown profile: the same answer?** In Q06-20 you said the existing profiles must not be listed. An error `UNKNOWN_PROFILE` versus `PROFILE_NOT_ALLOWED` tells someone which names exist.
    - [ ] A: one error for both (`INVALID_PROFILE`, a generic message, a 401/403); the real reason is only in the service's log
    - [ ] B: two errors, as in Q06-20
    *Default: A.*
    A:Default

16. **(!) The data policy "needs refinement" (Q06-24). Tell me what you meant.** Things I can think of; mark what matters to you:
    - [ ] a **provider** is `business` or `public` (as the default)
    - [ ] the **same provider** differs by plan: Google's free tier uses content to improve its products, a billed key does not, so "Google free" would be `public` and "Google billed" `business`
    - [ ] a policy per **step**, by what it reads (a step that reads tool answers needs `business`)
    - [ ] a policy per **data kind** (`public`, `internal`, `personal`, `customer`) that a step declares and a model must allow
    - [ ] **region** (the provider must process in the EU)
    - [ ] it also covers **Langfuse and the logs** (a step with business data must not send its text to a tracer that is not allowed; you mentioned placeholders in Q01-5)
    - [ ] other:
    A:What i meant that is an step for later refinement, the recontruction must be done in a way that later will be easy to apply that policies.

## E. Source of the files, startup and deployment

17. **(!) The files may come from other sources later (your Q06-30). What are those, and what must stay the same?** I would put a port in the application (`ConfigSourcePort`: `load_profiles()`, `load_flows()`, `load_steps()`, `load_prompt(name)`) and a first adapter that reads the repository's folders. Whatever the source, the data is a **snapshot read once at start**, checked by the same `assemble()`, and everything in the files is plain data (no Python inside a flow or a profile; hooks are named and resolved by the code). Questions:
    - Which sources do you foresee? (a database, S3 or a bucket, a configuration microservice, Git, a ConfigMap, a prompt-management service such as Langfuse prompts, ...)
    - Is it still **loaded at start only**, or do you expect it to change at run time in that future? (If yes, it breaks the rule of Q05-14 and needs its own proposal.)
    - Must each file carry a `schema_version` field, so a source of the future can serve an older format?
    - Do the **Python steps** (code) stay in the repository always, with only their JSON coming from outside?
    A:There can be many sources, like SQL, S·, langchain services. Yes, all is loaded at the start, for now there wont be any hot reaload. Yes. Yes.

18. **When one profile file is wrong, what does the service do?** Q06-6 says a startup error. With many profiles from different authors, one typo in a profile of the web chat would stop the robot too.
    - [ ] A: the service **does not start** (strict; the deploy fails and nothing reaches production)
    - [ ] B: the service starts, the wrong profile is **disabled** and logged at ERROR (`INVALID_PROFILE` for its clients), the others work
    - [ ] C: B in production, A in the tests and in `scripts/check_agent.py` (so a pull request cannot add a wrong profile)
    *Default: C.*
    A:Default

19. **An MCP server that is down when the service starts** (the Dynamics one is refused in this very session). A tool named in a profile can only be checked against the server's list when the server answers.
    - [ ] A: the **names of tools are checked at start** if the server answers; if it does not, the profile that uses it is disabled (as in 18 B) and tried again... never (a restart is needed)
    - [ ] B: the names are checked **at the first use**, the server being down only affects the messages that need it
    - [ ] C: the profile lists the names in a **snapshot** (as the contract snapshot of Q03), the check is against the snapshot at start, and the live list is only compared in a test
    *You also wrote that a profile may name a whole server **or** single tools, and that the agent must know where each tool comes from: I will use `server.tool` as the name; a profile that names a bare tool that two servers have is an error.*
    *Default: C.*
    A:Default

20. **The folder layout and the hexagonal layering (Q06-28 A).** Today `application/orchestration/` is one layer of the application (the tests in `test_orchestration_layout.py` keep the folders' dependencies one way). The proposal moves `steps/`, `flows/`, `profiles/` and `engine/` to the repository root.
    - [ ] A: root folders as in Q06-28; `application/` keeps the ports, the use cases (`SessionService`) and the domain; the new folders are **plain-data folders** (JSON, prompts) and the engine/steps code, which then import `application` and `domain`, never the reverse
    - [ ] B: the code goes under `application/` (`application/engine/`, `application/steps/`) and the JSON/prompt folders go at the root
    *Why it matters: A puts code at the root outside the `application` layer you have today, and the test of the folder layout must be rewritten; B keeps one place for code. The data folders (JSON, prompts) can be at the root either way.*
    *Default: B.*
    A:Default

21. **The cost tables of `docs/models/` (generated).** They compute the cost of "the big plan" of the conversation flow. With many profiles there is no single plan.
    - [ ] A: one table per profile, generated by a command from the assembled profile (`scripts/explain_profile.py <name>`, also useful to check a profile)
    - [ ] B: only for the profiles marked `tested`
    - [ ] C: leave the three tables for the `default` profile only
    *Default: A.*
    A:Default

22. **What would you hate to find out late (second time)?** Anything this file does not ask and your answers do not say; and, in your words, what is the first real use you want to see working at the end of the first stage that changes behaviour (stage 2: a client sends `robot` and its token and the robot behaves as today).
    A:

---

**When you finish:** say "Q07 answered". Then I rewrite PR-005 with the final model, open ADR-015, create epic T-05 with a task per stage, and mark Q05, Q06 and Q07 as processed in [00_README.md](00_README.md).
