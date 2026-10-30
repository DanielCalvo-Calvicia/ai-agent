# Q04 — Last clarifications before building T-01

**Answered by the maintainer on 2026-10-27 and processed** with Q03. Question 5 replaced the one-pull-request-per-task rule of Q01-16: everything goes on the one branch `feature_dynamics_mcp`.

Same format as Q01 to Q03: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets** or real hosts. Each question has my **default**.

Previous questionnaire: [Q03](Q03_refinement-and-good-practices.md) (answered 2026-10-27; questions 1, 2, 4, 5, 6, 9, 11, 12 and 13 took the default; question 7 chose no cache). **Q03 and Q04 are processed together** into the tasks once Q04 is answered. This is the last questionnaire before the build starts.

---

## A. Two answers of Q03 that I need to understand better

1. **Q03-8, what is kept between messages.** You wrote that the session stores "the response object, with all the workflow done", and that if the session is not new, the planner gets "the initial message + the response". I read it in three ways:
   - [ ] A: the planner gets the **original user message and the final reply** of each earlier exchange (what `AI_AGENT_HISTORY_TURNS` already keeps for triage and the project manager); nothing new is stored
   - [ ] B: also the **tool answers** of the earlier exchange (the table of orders the tool returned, after the data engineer cleaned it), so "and the second one?" can be answered without a new query
   - [ ] C: the **whole flow state** of the earlier exchange (the plan, every action and its output) is kept in the session
   Consequences to weigh: B and C keep customer data in the memory of the session until it ends (there is no expiry, Q01 and ADR-009) and make every later prompt longer and more expensive; C also sends that data to the model on every message.
   *Default: A, which is what exists. If you want B, say how many earlier exchanges may carry their tool answer (for example the last 2) and I will add it as a task of T-01.6.*
   A:A, there is no need to send the tools execution. For each request it generates a Reponse object. That object is stored as history of the session, so the next request of the same session can have access to this response object. So for the next request the initial input can add (apart from the incoming request) the initital request message and the output that is sent. This way the LLM can know the last request and what was the answear

2. **Q03-10, the per-MCP check.** You wrote that there is no need to verify the tools by default, but that an environment variable can turn on a check for each MCP. Two points:
   - **The variable.** Which shape do you prefer?
     - [ ] A: one variable per server, named from the server file: `AI_AGENT_CHECK_MCP_<NAME>=1` (for example `AI_AGENT_CHECK_MCP_DYNAMICS_MICROSERVICE=1`); unset or `0` means no check
     - [ ] B: one variable with a list: `AI_AGENT_CHECK_MCPS=dynamics_microservice,other`
   - **Where the result goes.** `GET /available` has a fixed contract in the bundled `contracts` wheel (it carries no field for it), so I cannot add the state of the MCP servers there without a new contract version. Options:
     - [ ] A: the check runs **at start-up and every time `/available` is called**, and the result is **logged** (a warning naming the server when it is not reachable); `/available` itself does not change
     - [ ] B: a new route `GET /available/mcp` in ai-agent (not in the contract) that returns the state of the checked servers
     - [ ] C: both
   *Default: variable A (one per server), result A (logged only).*
   A:Variable A. For now just log.

## B. Details of what you chose

3. **Q03-3, the cap on tool calls.** You asked for an environment variable: `0` means no limit, any other number is the limit, default 5. I will name it `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`.
   - What should happen when the cap is reached: the remaining calls are **not run**, and the reply says plainly that only the first N were done?
   - A value that is not a whole number or is negative: fall back to the default 5 with a warning (not `0`, so a typing mistake never removes the limit)?
   *Default: both as written.*
   A:1) it must say that it cannot use that many tool calls (personalized message via the last step of the flow). Yes

4. **The Claude model id.** Q02-8 chose "the same Sonnet model for every step". The catalog in `domain/value_objects/llm_request/model_catalog.py` has `claude-4-6-sonnet-latest`, `claude-4-5-sonnet-latest` and dated ids; the newest family of Claude models is not in the catalog.
   - [ ] A: `claude-4-6-sonnet-latest` (already in the catalog, no change)
   - [ ] B: another model: write the id as your enterprise account lists it (I add the row in T-01.3)
   - Is a cheaper model wanted for triage (step 1) and the editor (step 8) from the start? *Default: no, the same model for every step until the first real run shows the cost.*
   *Default: A, the same model on every step.*
   A:Default

## C. How the work is delivered

5. **Branches and pull requests.** Q01-16 chose one pull request per task. Today the epic branch is `feature_dynamics_mcp` (from `feature`) and holds only documents.
   - [ ] A: one branch per task, cut from `feature` (for example `feature_dynamics_mcp_t01_2`), each merged into `feature` by its own pull request; the documents (questionnaires, tasks) go first as their own pull request from `feature_dynamics_mcp`
   - [ ] B: one branch per task, cut from `feature_dynamics_mcp`, merged into it; the whole epic is merged into `feature` at the end
   - [ ] C: other (say how)
   *Default: A, the same flow as the documentation pull request that was already merged.*
   A:Not needed to generate a branch per task, make all on the same branch. All will be done on the branch feature_dynamics_mcp

6. **The documents so far.** Questionnaires Q01 to Q04, the task plan and the notes are written but not committed. Should I commit and push them now on `feature_dynamics_mcp`, before T-01.2 starts?
   - [ ] A: yes, one commit with a clear message, and I push it (you open the pull request and merge it)
   - [ ] B: yes, commit but do not push
   - [ ] C: not yet
   *Default: C (the project rule: never commit or push unless asked); say A or B when you want it.*
   A:C

7. **Recreating the venv.** `py -0` shows Python 3.14 and Python 3.11 on this machine; the README says the project runs on 3.14 on Windows, and `requirements.txt` was pinned with 3.14. I will use **3.14**, create the `windows` folder in the project (it is git-ignored) and run `pip install -r requirements.txt`. That downloads packages and installs the sibling `../shared-logging` in editable mode.
   - [ ] A: yes, create it with 3.14 when T-01.2 starts; I ask once more right before installing
   - [ ] B: use a different interpreter (say which)
   *Default: A.*
   A:Default
