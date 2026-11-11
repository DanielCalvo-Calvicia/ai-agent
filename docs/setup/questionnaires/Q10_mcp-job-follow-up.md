# Q10 — The follow-up of an MCP job, per server

**Asked and answered by the maintainer on 2026-11-11, and processed into T-07.1 and ADR-018.** Twelve questions took the default; question 9 chose **B** (two jobs in one answer: all or nothing), question 11 chose **B** (the shipment tools are offered in this epic), and question 12 took the default with a note (`dynamics_microservice` is being changed in another session). It decided [T-07.1](../../tasks/T-07_mcp-job-follow-up/T-07.1_decisions.md) and whether [ADR-018](../../decisions/ADR-018-mcp-job-follow-up-per-server.md) (proposed) is accepted as it is.

Same format as Q01 to Q09: write your answer after `A:`; mark an option with `[x]`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets**, real hosts or real customer data. Each question has my **default**, the answer I assume if you do not answer.

Where it comes from: a real call of 2026-11-11 to `customer_orders` on `Dynamics-Development` answered `note: pending: the query is still running as job <id> …`, not `status: running` with `next_offset`, which is what the operator prompt, the tests and the documents assume. The servers ai-agent reads from do not all have the same shape, and not all can be changed.

Previous questionnaire: [Q09](Q09_profiles-per-message.md).

---

## A. Which servers, and who can change them

1. **The servers ai-agent will read from.** Today: `dynamics_microservice` (ours, Streamable HTTP) and `aws_microservice` (SSE, used by nothing).
   - Which other MCP servers are planned, and for each one: can its maintainers change the shape of its job answers?
   - Does any of them have no jobs at all?
   *Default: only `dynamics_microservice` counts today; any new server starts as `job_protocol: none` until someone shows a real answer with a job.*
   A:Default

2. **The shape of 2026-11-11.** The `pending … job <id>` note and the `job_id`, `offset` lines of a finished read: is it the final shape of the Go service, or only a difference of the `Dynamics-Development` server?
   - [ ] A: final (the older `status: running` + `next_offset` is gone)
   - [ ] B: the service has both, by the kind of tool (workflow or generic)
   - [ ] C: unknown until T-07.2 is answered
   *Default: C; the agent supports both shapes either way (T-07.5).*
   A:Default

3. **The request to the Go service (T-07.2).** The prompt asks for one machine header (`status: ok | running | error`, `job_id`, `retry_after_seconds`, `next_offset`) and the same format for each table of a multi-table answer.
   - [ ] A: send it as written
   - [ ] B: send only part 1 (the questions); decide the change after reading the answers
   - [ ] C: do not send it; ai-agent adapts to what the service has
   *Default: A. The prompt says that ai-agent works without the change.*
   A:Default

## B. What the agent does

4. **Where the follow-up lives (ADR-018 decision 1).** The operator step (an LLM) follows a job today; the proposal moves it to the MCP adapter, as code.
   - [ ] A: code in the adapter; the operator never reads a job
   - [ ] B: keep the operator, only fix its prompt so it knows both shapes (cheaper, still depends on the model reading free text, does not cover two jobs in one answer)
   *Default: A.*
   A:Default

5. **How long it waits.** The whole message may wait 60 s for its tools (a constant). Between two reads of a job the proposal is 1 s, doubling, never more than 5 s.
   - [ ] A: as proposed (measured in T-07.9, then fixed)
   - [ ] B: other values (write them)
   - Is 60 s acceptable for a robot that speaks? A long silence is bad (Q01-10).
   *Default: A; if 60 s is too long for a voice, say the number you accept.*
   A:Default

6. **When the budget ends and the job still runs.** The proposal: cancel it (with the cancel tool the server file names) and say it is still running.
   - [ ] A: cancel it and say so
   - [ ] B: leave it running and say so (the result is lost anyway: nobody reads it)
   - [ ] C: say so and offer to ask again later (a second message of the user reads it; it needs the job id kept in the session)
   *Default: A. C keeps data and ids in the session memory with no expiry (ADR-009); not proposed.*
   A:Default

7. **What the user hears while it waits.** Today the robot is silent until the reply.
   - [ ] A: nothing different (the reply is spoken when the answer is ready)
   - [ ] B: a short spoken "one moment" when a job is found (needs Brain to ask for it; a change outside this repository)
   *Default: A.*
   A:Default

8. **An answer of a shape the protocol does not know.** The proposal: that action fails with a reason, its dependants are skipped, the writer tells the user the query could not be completed, one log line names the server and the outcome, never a value.
   - [ ] A: as proposed
   - [ ] B: also stop the whole message
   - [ ] C: treat it as a result (what happens today)
   *Default: A.*
   A:Default

9. **Two jobs in one answer** (`scope` all: open and archived orders).
   - [ ] A: follow each one apart; if one ends and the other does not, the reply gives the finished table and says the other is still running
   - [ ] B: all or nothing (if one does not end, none is given)
   *Default: A.*
   A:B

## C. The protocols and the files

10. **The `custom` protocol** (a pattern for the job id, the read tool, the offset parameter, the signs of "done" and "still running", all in the server file).
    - [ ] A: not now; it is built when a real server needs it
    - [ ] B: build it with the first protocols, to be ready
    *Default: A (it would be designed without a real case).*
    A:Default

11. **The shipment tools** (`order_shipments`, `shipment_status`, `shipment_tracking`) that the service lists today, and the `customer_no` pattern that now accepts `_`.
    - [ ] A: separate decision, later; they stay hidden until `allowed_tools` names them
    - [ ] B: offer them now, in this epic (adds their prompts, tests and documents)
    *Default: A.*
    A:B

12. **Rolling it out.** The agent is changed first and accepts both shapes; the server changes later.
    - [ ] A: agent first, server after, never at the same time
    - [ ] B: both on the same day, with the Go service keeping the old lines for a while
    *Default: A.*
    A:Default, i'm changing dynamics_microservice in anoter session

## D. How the work is delivered

13. **Branch.** T-07 touches `infrastructure/outbound/mcp/`, the operator prompt (a golden change) and the documents. The working branch today is `feature_deployment`.
    - [ ] A: a new branch `feature_mcp_job_follow_up` from `feature`, all of T-07 on it
    - [ ] B: on `feature_deployment`
    - [ ] C: other (say which)
    *Default: A (the deployment branch is a different piece of work, ADR-017).*
    A:Default

14. **The real run (T-07.9)** calls the real service (and, with `run_profile.py`, real models, which cost money).
    - [ ] A: ask me right before it, as the task says
    - [ ] B: the maintainer runs it
    *Default: A.*
    A:Default
