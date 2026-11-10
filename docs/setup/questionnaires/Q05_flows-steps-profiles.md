# Q05 — Flows, steps and profiles (before PR-005 is accepted)

**Vocabulary (corrected 2026-10-30 by the maintainer, Q06-5): agent = profile, workflow = flow.** In the answers below, "agent" means a profile and "workflow" means a flow.

Fills: [PR-005](../../proposals/PR-005-flows-steps-profiles.md), section 9 (the decisions D1 to D6) and everything the proposal assumed without asking.

Same format as Q01 to Q04: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets**. Each question says why it matters and my **default**, the answer I will assume if you do not answer. Questions marked **(!)** can change the design, not only a detail: answer those first.

---

## A. The goal itself (what I may have understood wrong)

1. **(!) What is a "profile" for you?** I assumed a *cost/quality recipe* (the way `proven`, `budget50`, `claude_mixed` are used today). It could also be:
   - [ ] A: a cost/quality choice for the same agent (cheap, balanced, quality)
   - [ ] B: a provider choice (all Google, all Claude, all Groq)
   - [ ] C: an **audience** or client (the robot, the web chat, another project each get their own agent)
   - [ ] D: an environment (dev, test, production)
   - [ ] E: several of these at once (say which)
   *Why it matters: A, B and D are one active profile for the whole service. C means **several profiles live at the same time**, chosen per request, and that changes the API and the router (see 2).*
   *Default: A and B, one active profile at a time.*
   A:A profile is a single configuration on what flows needs to be executed and which LLMs models are executed inside each stop of the flow. The profile my not use an specific flow, it may set the steps that needs to be done with the LLM specified or if not specified it gets the default. This way the profile can define which workflow should ir run with each LLM for each step of the workflow, and if it doesnt specify the workflow it specifies what steps it should do. The profile also can set the mcp available that the agent may use.

2. **(!) How many profiles are active at the same time, and who chooses?** You said the agent will serve the robot, a web chat and other projects.
   - [ ] A: one for the whole service, set by an environment variable and a restart
   - [ ] B: one per client, set by the client in `/session/start` (a new field, `profile`)
   - [ ] C: one per client, set by the service from who is calling (a key, a header, a list), the client cannot pick
   - [ ] D: one per message (the client may change it at any time)
   *Why it matters: B to D need a change in the API, in the sessions (a session keeps its profile) and a rule on what a client may ask for (a client must not be able to pick the most expensive model). PR-005 assumes A.*
   *Default: A now, B later as a separate proposal.*
   A:The profiles are selected via input of the client that uses ai-agent. All agentes can be used, this way the client sets what configuration it want to use.

3. **What is the real reason for the change?** Rank the reasons (1 = the main one):
   - [ ] trying models and prices faster without code changes
   - [ ] giving a different behaviour to each client or project
   - [ ] letting someone who does not write Python define a flow
   - [ ] making the code easier to understand and test
   - [ ] preparing for more flows (which ones?)
   *Why it matters: if the main reason is "someone who does not write Python", the files must be validated and friendly, and the tool to check them matters more than the engine. If it is "models faster", stage S2 alone gives most of the value.*
   *Default: models faster, then easier to understand, then more flows.*
   A:This is for making the ai-agent more independ and reusable. So creating and managing the request made by the client more easy to implement and work. Also in case of creating new profiles, flows or steps is easier. A clear separation of concepts will help a lot generating all those things, and implement them is easy tanks to the plug and play structure. Also given this structure each profile or workflow or step can set which mcps it can use. So the Request of selecting mcp_tools can be smaller.

4. **Which flows, steps and profiles do you already see coming?** Name them even if they are vague (for example "a flow that only searches Business Central", "a step that translates", "a profile for the web chat with no gestures").
   *Why it matters: the design must make **these** easy, not the cases I imagined. It is the best test of whether the abstraction is right.*
   *Default: none known; I design for the five flows that exist.*
   A:For now implement the existing ones. Now (if i'm not wrong) there are:
   - default: The one that uses the conversational flow + special
   - robot: The one that uses conversational + special + motion
   - dynamics: The one that uses special for using the mcp_tool of dynamics

5. **Who will write a new step, flow or profile?**
   - [ ] A: only you (a developer)
   - [ ] B: a developer of the team
   - [ ] C: someone who does not code (a profile or a flow as a file or in a screen)
   *Why it matters: A and B accept a Python decorator and a JSON file. C needs a stricter format, good error messages and probably a command that explains the result.*
   *Default: B.*
   A:All three, this will be done in a way that it uses json configuration to set each one.

## B. Words and boundaries (the likeliest source of misunderstanding)

6. **Is my reading of the three words right?** *Step* = one job (one LLM call, one call per action, or plain code). *Flow* = an ordered list of steps for one kind of message (`conversation`, `special`, `movement`, `expression`, `identification`). *Profile* = which model answers each step of each flow.
   - [ ] A: yes, as written
   - [ ] B: no (write what each word means for you; most important is *what a flow is*: today it is "a kind of message", not "a user-facing agent")
   *Default: A.*
   A:The profile is the configuration of the conbination of flows and steps.

7. **Is a profile only about models, or also about steps and flows?** Your objective 2 says "each profile follows a specific flow with specific steps with specific models". PR-005 lets a profile choose the model of every step and **drop optional steps**; a different order or a new step needs a new flow file (D2).
   - [ ] A: as in PR-005
   - [ ] B: a profile may only choose models (steps and flows are fixed)
   - [ ] C: a profile may also **reorder and add** steps freely
   - [ ] D: a profile **is** a flow (a profile names its own full list of steps; no shared flows)
   *Why it matters: C and D give the most freedom and the least safety: any contract check becomes the only protection. D also copies the same list of steps into every profile.*
   *Default: A.*
   A:The profile will set which flow do it run or wich steps should it do. This way a profile can be personalized at by the desired client.

8. **Does a profile hold prompts too?** A prompt tuned for Gemini may not be the best for Claude (today the Claude path also changes the schema, ADR-013).
   - [ ] A: no, prompts belong to the step, the same for every model
   - [ ] B: a step may have a prompt variant per provider; the profile picks it up through the model
   - [ ] C: a profile may name its own prompt file for a step
   *Default: A now. B if a run on a second provider shows a prompt that needs to change.*
   A:Yes, dependign on the step the systemprompt or the initial premessage can be different from the default of the steps

9. **Is `identification` part of this?** Every message goes through triage first and the router picks the flow from `task_category.domain`.
   - [ ] A: triage stays fixed; a profile may only change its model
   - [ ] B: a profile may replace the way a flow is chosen (for example a client that only has `conversation`)
   - [ ] C: a profile may remove triage (a client that always uses one flow, one call less)
   *Why it matters: C saves one model call per message, but then nothing sets `task_category`, `user_goal` or `constraints`, which the later steps read. It would need a different entry.*
   *Default: A.*
   A:The triage is just one step (mostly all flows or profiles will use it), but depednign on what the client want it may not need it

## C. What a profile may and may not do (safety, cost, data)

10. **(!) May a profile send customer data to any model?** The special flow gives Business Central answers to the data engineer, the writer and the editor (Q01-5, Q01-6: Claude, Langfuse for now). If a profile can put any model on any step, a profile could send that data to a provider you do not want.
    - [ ] A: no rule; whoever writes the profile is responsible
    - [ ] B: every model of the catalog says whether it may receive business data (`allowed_data: public | business`), and a step that reads tool answers needs `business`
    - [ ] C: the same as B, plus the provider is checked against a list you keep
    *Why it matters: with several clients (question 2) this is the one rule that stops a mistake in a profile from being a data leak. It is cheap to add now and hard to add after.*
    *Default: B.*
    A:C

11. **Is there a cost limit per profile?** Today the budget is a table (`config/budget.json`, 50 EUR per 1,000 messages) that is only read by a generated document.
    - [ ] A: still only a document
    - [ ] B: `assemble()` computes the cost of a full plan for the profile and **refuses** one above a limit you set in the profile
    - [ ] C: a real limit at run time (stop after N euros a day)
    *Default: A. B is easy once models and steps are data; C is a different feature.*
    A:Default

12. **Which steps may a profile never drop or replace?** My first list of *not optional*: `project_manager` and `action_executor` (nothing to execute without them), `draft_writer` in special (nothing to say). Candidates for *optional*: `safety_gate`, `editor_in_chief`, `answer_checker`.
    - **Is the safety gate really optional?** It decides whether a plan needs the user's confirmation. A profile without it can run any plan with no question.
    - [ ] A: optional (a trusted client may drop it)
    - [ ] B: never optional
    - [ ] C: optional only if the profile also says which tools are allowed
    *Default: B. It is the one step whose absence has a consequence outside the answer.*
    A:All steps are optional if the user that creates the flow or the profile misses somethign its there fault. All steps are optional.

13. **What happens when a model of a profile is out of capacity?** Today `fallback_models` is one list per profile (ADR-014). With models per step, a step on `claude-sonnet-5-5` and a step on `gemini-3.1-flash-lite` need different fallbacks.
    - [ ] A: a list per step in the profile; a list per profile as the default
    - [ ] B: still one list per profile
    - [ ] C: fallbacks may not cross providers (a Claude step falls back to Claude only)
    *Why it matters: a fallback to another provider is also a data decision (question 10).*
    *Default: A with the rule of question 10 applied to every fallback.*
    A:The profile, flow and step will set a list of ordedred LLMs that if the first one fails (with out of capacity) it gets the next

## D. Running it (changes, sessions, restarts)

14. **When may the configuration change?**
    - [ ] A: at start only (a restart is a deploy)
    - [ ] B: read again between messages (as `step_models.json` is today, by modification time)
    - [ ] C: through an endpoint
    *Why it matters: B means a flow definition can change between two messages of one conversation. C is a security surface (who may call it?). Hot reload also needs a rule for a paused run (question 15).*
    *Default: B for model choices, A for the list of steps and flows.*
    A:The configuration never change on runtime. All is set before the project is run. There is no way that the LLms of each part, steps, flows or profiles are changed at runtime.

15. **What happens to a user who was asked a question when the profile or the flow changes?** A paused run waits for the next message and resumes at a step by name (`PausedRun`).
    - [ ] A: the run keeps the profile and step list it started with until it ends
    - [ ] B: the run is dropped and the user is told to start again
    - [ ] C: not important (sessions live in memory and are lost on restart anyway, ADR-009)
    *Default: A.*
    A:That never happends the profile or flow or step never change at runtime.

16. **Should a reply say which profile produced it?** Useful for comparing runs, but it adds a field to `/session/message`.
    - [ ] A: no
    - [ ] B: yes, in the answer (`profile`, `models`)
    - [ ] C: only in logs and Langfuse
    *Default: C.*
    A:Default

17. **Is the environment variable still the way to override one model?** Today `AI_AGENT_MODEL_PHASE_<n>` (by number). PR-005 adds a name form and keeps the number as a legacy alias.
    - [ ] A: keep the number only
    - [ ] B: add the name form (`AI_AGENT_MODEL__SPECIAL__DRAFT_WRITER`)
    - [ ] C: remove the variables; everything in the profile file
    *Default: B, and the number stays until S6.*
    A:No, given that now will be a default profile, there is no need to keep it on env vars.

## E. Testing and quality (what I would hate to find out late)

18. **How should I prove that a profile works?** The suite is all mocks and runs without keys. Real runs cost money and have shown that a model can fail in ways a mock does not (Haiku's wrong greeting, T-03.6; Google 503 and 429, T-02).
    - [ ] A: the check of `assemble()` plus the mock suite is enough for the structure; real runs only by hand
    - [ ] B: each new profile needs a recorded real run (a small fixed set of messages) before it can be marked `tested`
    - [ ] C: the same as B, repeated when a prompt, a schema or a model of the profile changes
    *Default: B. Today the profiles say "Untested" in their `_about`; I would make that a field the tool shows.*
    A:Default

19. **May the golden file stay the safety net?** The golden file pins the exact LLM requests of the current default. For a new profile I would add one golden per profile **only for the structure** (which steps, which model), not for the content.
    - [ ] A: yes
    - [ ] B: no, one golden is enough
    *Default: A.*
    A:There is no need to genererate a golden per profile. Only the default is needed

20. **Is a stage allowed to leave the tests green and still change cost?** Per-flow models (S2) allow a profile that is much more expensive than before while nothing fails.
    - [ ] A: yes; the cost table in `docs/models/` shows it
    - [ ] B: no; a profile whose estimated cost grows more than N% against `proven` shows a warning
    *Default: A.*
    A:Default

## F. Scope, order and people

21. **(!) Can the work be done in the order S0 to S6?** Alternatives:
    - [ ] A: as written (registry, profiles, flows as data, router, contracts, cleanup)
    - [ ] B: profiles first (S2 alone, a quick win for models), the rest later
    - [ ] C: flows first (S3), because a new flow is what you need next
    - [ ] D: all at once in one branch (not recommended: the golden file then cannot tell which stage broke what)
    *Default: A, with a pause after S2 to decide if the rest is still wanted.*
    A:Default

22. **Is there something that must not break while this is done?** The robot (Brain calls `/session/message` once per utterance), the web chat when it exists, any demo with a date.
    - Say what is in use and when the next demo or delivery is. *Never write hosts or credentials.*
    *Default: nothing is in production; the API and the answer do not change.*
    A:Default

23. **Who reviews it, and how?** One pull request per stage (as T-01 did), or one for the epic.
    - [ ] A: one pull request per stage
    - [ ] B: one per epic
    - Branch: the work would start from `feature_reorganitzation` (the current one) or from `main`?
    *Default: A, from the current branch.*
    A:Default

24. **How much time or effort do you want to spend?** Rough size by stage: S1 and S2 small (a few files each), S3 and S4 medium (the flows and the router), S5 the largest (contracts on every step, one declaration per step), S6 documents and cleanup.
    - [ ] A: only S1 and S2 for now
    - [ ] B: S1 to S4
    - [ ] C: everything
    *Default: B.*
    A:Default

## G. Things you may not have thought about (my list; answer if any matters)

25. **A step in two flows with different state.** `draft_writer` runs in conversation and in special over the same `FlowState`, but movement and expression use their own state classes. A step reused in a flow with another state must work with both. Do you expect steps to be shared across flows, or is each flow's step set its own?
    - [ ] A: shared when they can be (as now)
    - [ ] B: never shared (each flow has its own copy of a step, a different name)
    *Default: A, and the contract check (`reads`/`writes`) says when it is not possible.*
    A:Default

26. **Metrics, cost tables and Langfuse are keyed by step name and phase number.** With per-flow models the same step can use two models in a run. Is it enough to see the cost per `(flow, step, model)`, or do you also need it per profile and per client?
    - [ ] A: `(flow, step, model)` is enough
    - [ ] B: also per profile
    - [ ] C: also per client (needs question 2 B to D)
    *Default: B.*
    A:All, i need to know each diffent combinations. Like each individual step, each flow and each profile

27. **Versions.** If a profile or a flow file changes, do you need to know which version produced an old answer (for an audit or a bug)?
    - [ ] A: no
    - [ ] B: yes: the profile name and a hash of the assembled agent go in the logs and in Langfuse
    *Default: B. It costs one line and is the only way to explain an old run.*
    A:Default

28. **A flow that calls no model at all.** Some flows are plain code (the motion validator, the gesture builder). Should a flow made only of code steps be allowed (for example a flow that answers "what time is it" with no LLM)?
    - [ ] A: yes, it is a normal flow
    - [ ] B: no, every flow needs at least one LLM step
    *Default: A.*
    A:Default

29. **Is there any part of the current code you do **not** want touched?** For example the schema tree, the golden file, the action executor, the MCP client, the Claude sanitizer. Anything listed here is excluded from the proposal.
    A:No ,everything may change, because the current directly structure may change, so the developmer can see cleanelt the separations

30. **Anything you expect from this change that is not in PR-005?** Write it as you would tell a colleague, even if it sounds out of scope. The most useful answer in this file is often the one that says "and I also thought it would...".
    A:

---

**When you finish:** say "Q05 answered". I will write the answers into PR-005 (a dated note and the decisions of section 9), open ADR-015 for what is decided, create the epic T-05 with one task per stage you accepted, and mark Q05 as processed in [00_README.md](00_README.md).
