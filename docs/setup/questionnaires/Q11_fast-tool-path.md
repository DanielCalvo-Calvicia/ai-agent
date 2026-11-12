# Q11 — The fast tool path: who calls it, how it is chosen, what it may do

**Asked and answered by the maintainer on 2026-11-11, and processed into T-08.1 and ADR-019.** Fourteen questions took the default. Three did not: question 3 chose **C** (two profiles on the same steps; the one with the triage is named `<server>_fast_triage`), question 4 chose **C** (the client is one thing today and uses one profile; **it was not said which**), and question 7 chose **B** (a profile can set its own steps with no flow file: the maintainer believed it was already done; the check accepts it but the runner refuses it, so it is a new task, T-08.10). Question 6 said "if default" (A). It decided [T-08.1](../../tasks/T-08_fast-tool-path/T-08.1_decisions.md) and whether [ADR-019](../../decisions/ADR-019-fast-tool-path.md) (proposed) is accepted as it is.

Same format as Q01 to Q10: write your answer after `A:`; mark an option with `[x]`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets**, tokens, real hosts or real customer data. Each question has my **default**, the answer I assume if you do not answer.

Where it comes from: a simple request ("How are my orders? I'm CL-1001") takes 37 to 46 s on the `dynamics` profile (8 model calls, measured on 2026-11-11). You asked for 20 s at most, **without a path written for one MCP server**: a common module, and profiles that choose the MCP servers and the steps. ADR-019 turns that into a flow `fast` (a tool selector, a tool caller in code, an answer writer) and a profile `dynamics_fast`.

Previous questionnaire: [Q10](Q10_mcp-job-follow-up.md).

How T-08.1 maps to this file: its questions 1 to 8 are Q11-1, Q11-3, Q11-5, Q11-6, Q11-7, Q11-9, Q11-13 and Q11-15. The rest is what the tasks also need.

---

## A. Who uses it, and how it is chosen

1. **The names.** The profile is what a client sends in `profile`; the flow is a file in `flows/`.
   - [ ] A: profile `dynamics_fast`, flow `fast`
   - [ ] B: other names (write them)
   *Default: A. A profile for another MCP server later would be `<server>_fast` on the same flow.*
   A:Default

2. **Who will call the fast profile, and how.** Today Brain makes **one call per utterance and sends no profile**, so it gets `default`. ADR-015 meant Brain to chain profiles (`identification`, then the profile of the answer), and that change is yours, later.
   - [ ] A: Brain will chain: it asks `identification`, reads the classification and asks `dynamics_fast` with it as `inputs`
   - [ ] B: a client that sends only the message (a web chat, the portal) must be able to use it too
   - [ ] C: both
   Why it matters: a profile that **requires** the classification (`inputs`) answers `MISSING_INPUT` to a client that does not send it, so it cannot be used until that client chains.
   *Default: C (the profile can work both ways: see question 3).*
   A:Default

3. **Does the fast flow classify the request itself?** One cheap triage call costs about 3 s and makes the profile work for a client that sends only the message.
   - [ ] A: no. The profile requires the `identification` result as `inputs` (`user_goal`, `task_category`): the fastest, but only for a client that chains
   - [ ] B: yes, a triage step inside the flow: it works for any client, about 3 s slower
   - [ ] C: two profiles on the same steps: `dynamics_fast` (A) and a variant with the triage (B) (two token hashes, two files)
   *Default: A if your answer to question 2 is A; C if it is B or C (the variant is one more JSON file, not code).*
   A:C, the name of the profile that has the triage would be <server>_fast_triage

4. **How the client chooses between `dynamics_fast` and `dynamics`.** The service does not route (ADR-015): the client chooses.
   - [ ] A: by the classification: `domain` data and low complexity go to the fast profile, anything else to `dynamics`
   - [ ] B: always the fast profile first, and `dynamics` when the fast one says it cannot (see question 6)
   - [ ] C: the client is one thing today (say which) and always uses one profile; the choice is not needed yet
   *Default: C for now, A when Brain chains.*
   A:C

## B. What it may do

5. **The read-only check.** The fast path has no safety gate step, so it must run only tools that change nothing. The MCP annotation `readOnlyHint` says it; the Dynamics tools already carry it. The check is at run time (the annotation is on the live server).
   - [ ] A: a tool is run only if the profile allows it **and** it carries `readOnlyHint`; a tool without the hint is refused
   - [ ] B: as A, but a tool the profile names **one by one** (`tools.tools`) is allowed even without the hint (you answer for it)
   - [ ] C: no annotation check: the profile's tool list alone decides
   *Default: A.*
   A:Default

6. **A request that needs more than one tool** (for example "my orders and where is the parcel") or that depends on a previous result.
   - [ ] A: the reply says it plainly and briefly; the client picks `dynamics`
   - [ ] B: as A, plus a structured line in `output` (for example `{"needs": "dynamics"}`) so the client can retry by itself; it adds a field to the API and its documents
   - [ ] C: the fast profile hands the request to the full flow itself (it is a router inside the service, which ADR-015 rejected; I would not do it)
   *Default: A; B later if Brain wants it.*
   A:If Default

## C. How the steps and the servers are switched

7. **Different steps for a different profile.**
   - [ ] A: one **flow file** per variation (`flows/fast.json`, `flows/fast_checked.json` with a gate, ...); the profile picks it with `flow`. It works today and needs no code
   - [ ] B: also make a profile's inline `steps` runnable, so a profile can list its steps without a flow file (work in the flow loader; the check already accepts it and the runner refuses it)
   Which variations do you already want? (for example one with a gate, one with the triage, one with the editor): write them.
   *Default: A, and no variation beyond question 3.*
   A:B, but there is no varianton as today, but a profile can set its own steps without needing flow (i thought that was already done)

8. **Which other MCP servers will use this module soon?** It decides how generic the selector prompt and the tool rules must be.
   *Default: none yet; only `dynamics_microservice`. The module is still written without any server name, and a test enforces it.*
   A:Default

## D. Models, time and cost

9. **Models.** Haiku 4.5 is faster; Sonnet 5.5 is steadier.
   - [ ] A: Haiku on the selector and on the writer; Sonnet only if the quality fails
   - [ ] B: Haiku on the selector, Sonnet on the writer
   - [ ] C: Sonnet on both
   - [ ] D: other (write it)
   *Default: A. The profile gets its own model set (name decided in T-08.5).*
   A:Default

10. **What exactly the 20 s measure.**
    - [ ] A: the request to the fast profile, from the message to the answer (my estimate is 8 to 14 s, not measured)
    - [ ] B: the whole chain of the client: `identification`, the fast profile, `gesture` (each adds a call; about 3 to 5 s for `identification`)
    - [ ] C: the above plus the spoken reply
    And the statistic: [ ] the median of 5 runs, [ ] 9 runs of 10 under 20 s.
    *Default: A and the median of 5 runs (the criterion of ADR-019).*
    A:Defaut

11. **How many real runs may I make?** Every run of one message costs about 0.05 to 0.09 USD (T-08.2 to T-08.7 and T-08.9: roughly 40 messages, 2 to 4 USD).
    - [ ] A: ask before every run (the project rule)
    - [ ] B: a budget: up to N USD in the epic without asking each time (write N), the local Dynamics service only
    *Default: A.*
    A:Default

12. **If two model calls are still above 20 s** after the tuning of T-08.7.
    - [ ] A: stop and ask you (the alternatives are in the ADR: the triage and the gate, or one single step that uses the tool itself)
    - [ ] B: try the alternatives in that order by myself, within the budget of question 11
    *Default: A.*
    A:Default

## E. The existing profiles

13. **Use the direct call also in `special` and `dynamics`.** An independent tool action would be called by code, and the LLM operator would run only for an action that depends on another. Their golden calls change (the `phase5` and `phase6` calls of those scenarios go away), on purpose.
    - [ ] A: yes
    - [ ] B: no, only the new flow uses it
    *Default: A.*
    A:Default

14. **The extra action the planner adds** (the cognitive worker did 396 tokens of nothing on a plain read). Fixing it is a prompt change of `dynamics` and `special`, with its own before and after (the T-06 rule).
    - [ ] A: not in this epic; the fast profile replaces that path
    - [ ] B: yes, as one more task of this epic
    *Default: A.*
    A:Default

## F. Delivery

15. **Branch and commits.**
    - [ ] A: `feature_fast_profile` (created from `origin/feature`), commits only when you ask, you open the pull request
    - [ ] B: other (say how)
    *Default: A.*
    A:Default

16. **The token of the new profile.** A profile needs a client token; the file holds only its SHA-256, and the token must reach the client (Brain, the portal) once.
    - [ ] A: I generate a random token and show it to you **once, in this chat**; only the hash goes in the file
    - [ ] B: you generate it (I give you the command) and send me the hash
    *Default: A.*
    A:Default

17. **The Dynamics URL of the environments.** The `.env` of this machine points at an older service (no shipment tools, no `status` line), and the real runs of T-07.9 used the local Docker service. For a deployed environment to run the fast profile with the shipment tools, `DYNAMICS_MCP_URL_DEVELOPMENT` and `DYNAMICS_MCP_URL_PRODUCTION` must point at the new service.
    Do they already? (`UNKNOWN` is fine; write where it is decided, never the address.)
    *Default: UNKNOWN; the real runs of this epic use the local service set in the shell, and nothing is deployed by this epic.*
    A:Default
