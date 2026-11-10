# Q06 — Follow-up of Q05 (what your answers changed or left open)

**Vocabulary (corrected 2026-10-30 by the maintainer, Q06-5): agent = profile, workflow = flow.** Where this file says "agent" or "workflow" in a question, read "profile" and "flow".

Fills: [PR-005](../../proposals/PR-005-flows-steps-profiles.md), which I will rewrite after this file. Your answers in [Q05](Q05_flows-steps-profiles.md) changed the design a lot: PR-005 assumed one profile for the whole service, models only, a fixed flow list and environment overrides. Your answers say something bigger. Section 0 is my reading of them: **correct it first**, because every other question depends on it.

Same format as Q01 to Q05: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets**. Each question has my **default**, the answer I will assume if you leave it empty. **(!)** = it can change the design.

---

## 0. What I understood (confirm or correct)

> A **profile** is the complete configuration a client asks for. It says (a) which flows run, or directly which steps run, (b) which models answer each step, in an ordered list where the next model is used when the first is out of capacity, (c) which MCP servers and tools the agent may use, and (d) for a step, its own system prompt or initial pre-message instead of the default. The client **chooses the profile on each session** (many profiles live at the same time). The files (profiles, flows, steps) are JSON, written by developers or by people who do not code, and **never change while the service runs**. Every step is optional: a wrong profile is the author's fault. Environment variables stop overriding models. Metrics are kept per step, per flow and per profile. The profiles you see coming: `default` (conversation + special), `robot` (conversation + special + movement) and `dynamics` (special, with the Dynamics MCP tools).

0. **Is that right?** Write what is wrong, even a word.
   A:All you said is true

---

## A. Profile, flow and step: the exact boundaries

1. **(!) What is the difference between a profile that "runs a flow" and one that "lists steps"?** You wrote that a profile may name a flow, or, if it does not, name the steps. I read it as two forms:
   - form 1: `"flows": ["conversation", "special", "movement"]` (existing flows; the router picks one by domain, as today)
   - form 2: `"steps": ["triage", "project_manager", "action_executor", "draft_writer"]` (an anonymous flow written inside the profile; no router)
   - [ ] A: both forms, a profile uses one or the other
   - [ ] B: both forms, and a profile may mix them (some flows plus extra steps)
   - [ ] C: only form 1 (a flow is the only place where an order of steps is written)
   *Why it matters: form 2 means the order of steps is written in many places and cannot be reused; C keeps one place for it and a "custom" profile creates its own flow file. B is the hardest to validate.*
   *Default: A.*
   A:For each profile there is only one flow or a list of steps. This way the client just need to ask to use a profile and the ai-agent already know what it needs to do. Now the flows are mixed, they will be redone and reorganized to fit the new requirements. The steps now have clear separation, but they arent orgaanized in a way that are easy to plug and play

2. **(!) With several flows in one profile, who chooses between them?** Today triage sets `task_category.domain` and `FLOW_BY_DOMAIN` maps it. For `robot` (conversation + special + movement) that is the rule. For `dynamics` there is only `special`.
   - [ ] A: the same rule for every profile: the domain picks the flow; a domain with no flow in the profile goes to the profile's `default_flow`
   - [ ] B: each profile writes its own table (`"routing": {"movement": "movement", "*": "special"}`)
   - [ ] C: a profile with one flow skips triage and the routing altogether
   *Why it matters: `dynamics` with a "communication" message (a greeting): A sends it to `special`, which plans and calls tools for a greeting. C also removes the triage call.*
   *Default: B, and a profile with one flow still runs triage unless it drops it (question 4).*
   A:Each profile will just have one flow or a list of ordered steps

3. **Does `robot` include the gestures (the expression flow) and `default` not?** Today the gesture runs for every conversation and special reply (`AI_AGENT_EXPRESSION`, default on). A web chat has no arms.
   - [ ] A: only profiles that list it (`robot` yes, `default` and `dynamics` no)
   - [ ] B: all three, as today
   *Default: A.*
   A:The expression flow may be used by other profiles.

4. **(!) A profile with no triage: where do `task_category`, `user_goal` and `constraints` come from?** You said a client may not need triage. The planner and the writers read those fields. Options:
   - [ ] A: a profile may declare **fixed initial values** (`"initial_state": {"task_category": {"domain": "special"}}`)
   - [ ] B: the steps that need them are not allowed after a missing triage (the startup check refuses it)
   - [ ] C: a lighter, cheaper step replaces triage (the profile says which)
   *Default: A, with B as the error when a step reads something nobody provides (see question 6).*
   A:I said that because some flows may just need to make some specific steps. Like it may only need to ask something to an mcp and then run the draft_writter and the editor_in_chief

5. **What are "profile", "flow" and "agent" to you?** You wrote "all agents can be used" and "workflow". In the code today `CLAUDE.md` says "a new agent = its file in flows/".
   - [ ] A: agent = profile (what the client picks); flow = a list of steps; workflow = flow
   - [ ] B: agent = flow
   - [ ] C: other (write it)
   *I will use A in the documents and drop "agent" for flows.*
   *Default: A.*
   A:Sorry what i mean are agent = profile and workflow is a flow. Replace the last questionare with the corrent names, so there is no confusion.

6. **(!) You said every step is optional, and the author is responsible. Which mistakes should still stop the service from starting?** Not "dropping the safety gate", but things that cannot work at all:
   - (i) a step reads a field that no earlier step writes and no `initial_state` gives (it would fail on the first message)
   - (ii) no step produces the final text of the reply (the answer would always be empty)
   - (iii) an unknown step, flow, model or MCP name, a typo in a key
   - (iv) a model that cannot do what the step needs (for example a three-level nesting limit, ADR-013)
   - [ ] A: all four are errors at startup
   - [ ] B: (ii) and (iii) are errors; (i) and (iv) are warnings in the log
   - [ ] C: only (iii)
   *Why it matters: you do not want to guess which rule you are breaking at 2 a.m., and a warning is easy to miss. Dropping a gate is the author's decision; a step that reads nothing is not.*
   *Default: A. The safety gate itself stays optional, as you said.*
   A:Default

7. **(!) May someone who does not code create a step completely in JSON?** You said all three (developer, team, non-coder) will write steps, flows and profiles in JSON. A step today is Python (`build_input`, `apply`), a prompt and a schema in `full.schema.json`. For a non-coder it would have to be:
   - [ ] A: **declarative**: `{"name": "translator", "prompt": "prompts/translator.txt", "reads": ["reply"], "output_schema": {...}, "writes": "reply"}` with no Python; the engine fills a generic `state.values` bag
   - [ ] B: Python steps are written by a developer; a non-coder only combines existing steps into flows and profiles
   - [ ] C: both (a declarative step is a *kind* of step next to the Python ones)
   *Why it matters: A and C are a large feature (a generic state, a JSON output schema checked at startup, the Claude sanitizer applied to it); B is much smaller and covers "profile and flow" for non-coders. This is the biggest cost question in this file.*
   *Default: C, but the declarative step is its own stage after the rest (it needs nothing from the others).*
   A:Yes, given that now the configuration of each step will be done via json.

8. **Can a profile extend another one?** `robot` is `default` plus movement; `dynamics` is `default` with different MCP tools and models. Without this, every profile repeats the model table.
   - [ ] A: yes, `"extends": "default"` and only the differences are written
   - [ ] B: no, every profile is complete; a shared piece (a **model set**) can be named and reused
   - [ ] C: both
   *Default: C.*
   A:B

9. **What happens with the ten profiles in `step_models.json` today?** (`proven`, `budget`, `balanced`, `quality`, `budget50`, `claude_sonnet`, `budget50_groq`, `google_free`, `claude_haiku`, `claude_mixed`.) They are tables of models, with no flows, so under your definition they are not profiles.
   - [ ] A: they become **model sets** that a profile names (`"models": "claude_mixed"`) and the three new profiles are the ones the client picks
   - [ ] B: each one becomes a full profile (flows, steps and models)
   - [ ] C: most are removed; keep only the ones that were run (`proven`, `claude_haiku`, `claude_mixed`) and say which
   *Default: A, and I remove the ones marked "Untested" and not referenced (my list, for you to cut).*
   A:They will become an specific profile, but that needs to be tested by the developer, because some of them might not be neeeded now. They will serve as generic profiles

## B. MCP servers and tools

10. **(!) At which level are the MCP tools chosen, and how do the levels combine?** You said a profile, a flow or a step can each set the MCP it may use.
    - [ ] A: **the narrowest wins**: the tools a step can use are the intersection of what the profile, the flow and the step allow (nothing set = no restriction at that level)
    - [ ] B: the **most specific replaces** the broader one (a step's list replaces the flow's, which replaces the profile's)
    - [ ] C: only the profile and the step
    *Why it matters: with A a flow cannot give a step a tool the profile does not allow (safer). With B a step can widen the list by mistake. It also decides how the allowed-tools list of `mcps/dynamics_microservice.json` fits (Q03).*
    *Default: A.*
    A:Default

11. **Does choosing the tools also change what the planner sees?** Today the whole tool list is given to the project manager. You said the request of selecting tools "can be smaller". That is two things: what the model is *shown* (fewer tokens) and what it may *call* (the cap).
    - [ ] A: both; a tool outside the profile is neither listed nor callable
    - [ ] B: only callable (the list shown is unchanged)
    *Default: A.*
    A:Default

12. **Where does each MCP server live now?** Today `mcps/*.json` plus `DYNAMICS_MCP_URL`. Per profile a client may need a different server or the same server with different allowed tools.
    - [ ] A: servers stay in `mcps/` and are named in profiles; the URL is in the environment
    - [ ] B: the URL may also be given per profile (never a key; keys and URLs of private networks stay in the environment, the profile names the variable)
    *Default: A.*
    A:Default, but there are two types of selection, te full server tools or specific tools (they may not specify the server, so the agent needs to know where it comes from)

## C. Prompts per profile

13. **(!) What exactly may a profile change in a prompt?** You wrote "the system prompt or the initial pre-message can be different from the default of the step".
    - [ ] A: **replace** the whole prompt file of a step for this profile (a new file)
    - [ ] B: **add** text to the default prompt (a persona or house rules, appended or prepended), the default stays
    - [ ] C: both
    *Why it matters: a replacement prompt must still fit the schema (the answer format is in the schema, not only the prompt; `docs/rules/schemas-and-prompts.md`). An addition cannot break the format. A client that wants "a friendly tone for the robot" needs B; "a different job for the step" needs A.*
    *Default: C, with A allowed only for steps whose schema is unchanged.*
    A:Default

14. **Where does the text live?** In the profile file, or in a file next to it?
    - [ ] A: always a file in `prompts/` (as today; easier to read and diff), the profile names it
    - [ ] B: a short text may be written inside the JSON
    *Default: A.*
    A:Both, it can be set via file or directly on the field.

15. **Is the default language and persona part of this?** Today the reply language follows the user (Q01-4). A profile for the web chat may need another style.
    - Do you already know a difference between the robot, the web chat and the Dynamics assistant (tone, length, formality, language, what to never say)? If yes, write it; it will be the first real use of question 13.
    A:No, it needs to follow the user language

## D. The client and the API

16. **(!) Is changing the API contract allowed?** `/session/start` and `/session/message` are built from `contracts.api.microservices.ai_agent.session.*`, which comes from a **different repository** (`../contracts`), bundled into `vendor/` as a wheel; Brain is the current client. A `profile` field needs a new version of the contract, a bundle and a change in each client.
    - [ ] A: yes, I own `contracts` and will release it; the field goes in `/session/start` (the profile is fixed for the session)
    - [ ] B: yes, in `/session/message` (a client may change it at any time)
    - [ ] C: both, `/session/start` sets the default and `/session/message` may override it
    *Why it matters: with B or C a paused run (a question to the user) and the history must stay valid when the next message uses another profile; with A there is nothing to solve. Your Q15 answer ("never changes") is true of the files, not of the choice made by the client.*
    *Default: A.*
    A:Default, it needs to update the docs apis so later on i can modify the contracts

17. **(!) What does the robot do today, and what happens to Brain until it sends a profile?** Brain sends no profile now and the robot **uses movement and gestures today**. Under your definition `default` has no movement.
    - [ ] A: a client with no profile gets the profile named in a config file (`"default_profile": "robot"` for now), so Brain keeps working untouched; `default` stays the name of the plain conversation + special profile
    - [ ] B: a client with no profile gets an error (`UNKNOWN_PROFILE`) and Brain must be changed first
    - [ ] C: the profile called `default` is the one used with no profile, and I make it the same as today (all flows incl. movement and gestures); `robot` is then the same, with another name
    *Why it matters: it is the difference between "nothing breaks" and "the robot stops moving until another repository is released". Today nothing is in production (Q05-22), so B is possible.*
    *Default: A.*
    A:C. The robot flow will have its own profile, separated of the default one.

18. **May any client use any profile?** You answered "all can be used". Two risks: a profile with expensive models, and a profile that reaches the Business Central tools (customer and order data, Q01-2: "there will be multiple users").
    - [ ] A: yes, any client, any profile (a profile that reaches business data is the author's responsibility, like question 6)
    - [ ] B: each profile says `"public": true/false`; a client may only pick public ones, others need a key or a list (the service knows who calls)
    - [ ] C: the same as B, and Brain and the web chat get only the profiles you list
    *Default: B; the profile with Dynamics is not public.*
    A:There will be a token for each profile, so it can verify that the selected profile has the token that its really doing, so its like an extra verification

19. **How does the service know who the client is?** Needed for question 18 and for your metrics "per profile and each combination" (Q26). Today there is `user_id` and `username` in the session and nothing about the client application.
    - [ ] A: a new field `client` in `/session/start` (a name only, trust-based)
    - [ ] B: from an API key or a header the service checks
    - [ ] C: not needed now; metrics by profile only
    *Default: A, and B when question 18 is B or C.*
    A:Default

20. **What does the client do when the profile is unknown or not allowed?** And can it ask which profiles exist?
    - [ ] A: `/session/start` fails with an `error_code` (`UNKNOWN_PROFILE`, `PROFILE_NOT_ALLOWED`) and the message is clear; nothing else
    - [ ] B: A, plus a `GET /profiles` that lists the public ones (name, description, flows)
    *Default: B.*
    A:A, there cant be listed which profiles exists, that is mandatory for security reasons

## E. Files, deployment and the models

21. **Where do the JSON files live at run time?** "Never changes while it runs" means a file is read at start. A non-coder who edits a profile needs a place to do it.
    - [ ] A: in the repository (`config/`), changed through a pull request, deployed with the service
    - [ ] B: in a folder outside the code (a mounted volume or a ConfigMap in Kubernetes, Q01-7) named by one variable (`AI_AGENT_CONFIG_DIR`), so a profile can change without a release
    - [ ] C: A for flows and steps, B for profiles
    *Why it matters: B means a bad edit is found when the service starts (the checks of question 6 matter more), and the deployment must keep the old version if the new one fails to load.*
    *Default: C.*
    A:The files live whre they were. What i mean of a non-coder is that befor deployment they need to set up the profiles they need. In case they made a bad choice they need to redeploy with the changes, fow now

22. **Which of the settings in the environment move into the profile?** Today `AI_AGENT_PARALLEL_ACTIONS`, `AI_AGENT_MAX_ATTEMPTS`, `AI_AGENT_HISTORY_TURNS`, `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`, `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS`, `AI_AGENT_EXPRESSION`, `AI_AGENT_RETRY_WAIT_SECONDS`.
    - [ ] A: all of them may be set per profile; the environment holds the **default** for all profiles
    - [ ] B: only the ones that change behaviour for a client (history turns, MCP caps, expression); the rest stay global
    - [ ] C: none; only the models, steps and tools move
    *Default: B.*
    A:Default

23. **Fallback lists at three levels (your Q13).** The profile, the flow and the step may each name an ordered list of models. If a step has a list, does it replace the flow's, or are they joined (step first, then flow, then profile)?
    - [ ] A: the narrowest list replaces the broader ones
    - [ ] B: joined in order: step, flow, profile, without repeats
    *Also: every model in any list obeys the data rule of Q05-10 C (an allowed provider, `business` for steps that read tool answers).*
    *Default: B.*
    A:The order is profile sets a model, then the flows and the steps use that. If the flow sets a profile, the steps use that profile. Like from up to down

24. **The data rule (Q05-10 C): where is the list of allowed providers?** A file you keep, outside the profiles.
    - [ ] A: `config/data_policy.json` in the repository: `{provider: "business" | "public"}`
    - [ ] B: the same, plus a different list per environment (production stricter than development)
    - Which providers are `business` today? (Q01 said Claude for tool data; write the others or `LATER`.)
    *Default: A; only Anthropic is `business`, the rest `public`.*
    A:Default, but this needs refinement

25. **Model catalog and prices are the same for every profile?** Yes today (`config/*_models.json`). A client with its own contract or its own key per provider would need another price list or key.
    - [ ] A: one catalog, one set of keys for the service
    - [ ] B: a profile may name a different key variable per provider (never the key)
    *Default: A.*
    A:Default

## F. Metrics, testing and migration

26. **How is a combination named in the metrics?** You need each step, each flow and each profile. One record would carry `profile`, `flow`, `step`, `model`, `client`, tokens and cost. Langfuse gets the same as tags.
    - [ ] A: yes, as written (a record per LLM call with those five keys; totals by any of them are computed from the records)
    - [ ] B: A plus a **cost per message** for the whole assembled agent in the logs
    *Default: B.*
    A:Default

27. **Testing with the real models.** You asked for only the golden of the default (Q05-19). A profile with an overriding prompt or an unusual model has no automatic check beyond the startup rules.
    - [ ] A: accepted; real runs by hand
    - [ ] B: a small set of fixed messages (a greeting, a plan, a movement, a Dynamics question) that I run against a profile with one command and write the result in the profile's note (`tested: 2026-..`); it costs a few cents per profile
    *Default: B (the command only; you decide when to run it).*
    A:Default

28. **The folder layout.** You said the current structure may change so the separations are clear. A possible target:
    ```text
    ai-agent/
      steps/            Python steps (+ declarative ones later), one file each
      flows/            JSON: one per flow (+ hooks/)
      profiles/         JSON: one per profile; model_sets/ next to it
      mcps/             as today
      prompts/          as today; per-profile prompts in prompts/profiles/<name>/
      schema/           as today
      engine/           pipeline, runner, assemble (no knowledge of any flow)
    ```
    - [ ] A: yes, JSON next to the code in the repository root, `application/orchestration/` is cut into `engine/` and the rest
    - [ ] B: keep `application/orchestration/` and put the new folders inside `config/`
    - [ ] C: other (draw it)
    *Why it matters: A renames many paths (tests, docs, imports, `CLAUDE.md`, the golden); it is one stage with no behaviour change and is worth doing **first** if you want it.*
    *Default: B now, A as its own stage only if you ask for it.*
    A:A

29. **Order of stages after your answers.** Stages change (profile per client, MCP scoping, prompts per profile, generic steps are new). My new order:
    1. folder layout and the step registry (no behaviour change)
    2. profiles with flows, models, fallback lists, model sets; `assemble()` and its checks; the API field and `default_profile`
    3. flows as JSON; the router from the flows of the profile
    4. MCP scoping (profile, flow, step); tools shown to the planner
    5. prompts per profile
    6. metrics by profile and client; the data policy
    7. declarative steps (question 7), the explain command and the real-run command
    - [ ] A: yes
    - [ ] B: change it (write the order you want; say which stage is needed first by a client)
    A:A

30. **What would you hate to find out late?** And, as in Q05-30: anything you expect from this change that is not written in PR-005 or in this file.
    A:That the prompts and profiles and flows may come from a different source, now they come from local files, thats okey for now. But in the future will come from different providers, it needs a structure that later on this addition wont affect as much.

---

**When you finish:** say "Q06 answered". I will rewrite PR-005 (the model of section 0, the decisions, the new stages), open ADR-015, create epic T-05 with a task per stage, and mark Q05 and Q06 as processed in [00_README.md](00_README.md).
