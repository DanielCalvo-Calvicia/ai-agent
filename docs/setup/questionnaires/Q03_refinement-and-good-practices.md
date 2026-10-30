# Q03 — Refinement and good practices before building T-01

**Answered by the maintainer on 2026-10-27 and processed** with [Q04](Q04_last-clarifications.md) into [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) (*Resolution*) and the tasks (new: T-01.10, T-01.11, T-01.12).

Same format as Q01 and Q02: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets** or real hosts. Each question says why it matters and my **default**, the answer I will assume if you do not answer.

Previous questionnaires: [Q01](Q01_dynamics-mcp.md), [Q02](Q02_after-q01.md) (both processed). These questions came from reading the code paths the epic touches: they are about safety, failure and cost, not about what the feature does. Fills: [T-01.2](../../tasks/T-01_dynamics-mcp/T-01.2_streamable-http-transport.md), [T-01.3](../../tasks/T-01_dynamics-mcp/T-01.3_server-config-and-settings.md), [T-01.4](../../tasks/T-01_dynamics-mcp/T-01.4_mcp-timeouts.md), [T-01.6](../../tasks/T-01_dynamics-mcp/T-01.6_planner-guidance-and-jobs.md), [T-01.7](../../tasks/T-01_dynamics-mcp/T-01.7_verification.md).

---

## A. Safety

1. **Tool answers are untrusted text.** An order or customer record can hold free text (a name, an external document number, a note). That text is placed in the prompt of the data engineer, the writer and the editor. A hostile value such as "ignore your rules and ..." must be treated as data, never as an instruction.
   - [ ] A: yes: the prompts say that tool results are data only, and T-01.7 has a scripted scenario with an injected sentence that must not change the plan or the reply
   - [ ] B: no extra work
   *Default: A.*
   A:Default

2. **Allowed tools on the ai-agent side.** The Go service decides which tools it exposes (`MCP_EXPOSE_GENERIC_TOOLS=false`), but a misconfigured deployment could expose `run_query` again, and ai-agent would offer it to the planner.
   - [ ] A: the server file lists the tools ai-agent may use (`customer_orders`, `order_status`, `customer_card`, `get_guidance`, `list_workflows`, `get_job_result`, `cancel_job`); any other tool the server offers is hidden from the planner and logged as a warning
   - [ ] B: trust whatever the server offers
   *Default: A (defence in depth). The list lives in `mcps/dynamics_microservice.json`, so a new tool is a one-line change and a deliberate one.*
   A:Default

3. **A cap on tool calls per message.** A plan can contain many actions and each MCP action is one LLM call plus one tool call plus one more LLM call. A confused plan could loop over many customers.
   - How many Dynamics tool calls at most per message? (for example 5; the rest are not run and the reply says so)
   *Default: 5.*
   A:lets make a env vars for this, that if its 0 there is no limit, if its different than that it gets that value. We can make by default 5.

## B. Failure and cost

4. **Retries of tool calls.** `AI_AGENT_MAX_ATTEMPTS` (3) also retries a failed MCP tool. With a 30 s call limit (T-01.4), three attempts could take 90 s, longer than the 60 s total wait you chose in Q01-10. The tools are read-only, so a retry is safe, but a timeout is not a reason to retry.
   - [ ] A: retry only a transport error and `error (retry_later)`, once; never retry a timeout, `input`, `not_found`, `source_problem` or `internal`
   - [ ] B: keep the global rule (up to three attempts for any failure)
   *Default: A.*
   A:Default

5. **The Go service is down or unreachable.** Listing its tools gives an empty list (10 s limit), and the project manager is still told the server exists, so it may plan a call that cannot run (a known gap today for stdio servers).
   - [ ] A: a server that offers no tools is hidden from the planner for that message, and when the user asks for Business Central data the reply says honestly that it is not reachable now
   - [ ] B: keep today's behaviour
   *Default: A, with the listing cached for a short time (60 s) so a down server costs at most one 10 s wait per minute.*
   A:Default

6. **Total time of one message.** A request that reaches the tool goes through triage, project manager, safety gate, MCP operator, data engineer, writer and editor (several model calls) plus the tool wait (up to 20 s on the Go side, 60 s total with the follow-up). The caller (the web chat or Brain) has its own timeout for `POST /session/message`.
   - What is the longest the caller waits for an answer (seconds)? If you do not know, say `UNKNOWN` and I will measure it in T-01.9.
   *Default: UNKNOWN; the number is recorded in `docs/operations/monitoring.md` after the first real run.*
   A:Default

7. **Repeated identical queries.** Two users asking for the same customer within seconds make two tool calls and two sets of LLM calls.
   - [ ] A: no cache (always fresh, simplest)
   - [ ] B: a short cache of tool answers per customer code (seconds), in memory
   *Default: A. A cache of customer data in memory is also another place where that data lives.*
   A:A, the agent will not have any cache of the requests, different request are treated as two separate things.

## C. Memory and observability

8. **Follow-up questions.** "And the status of the second one?" needs the earlier tool answer. Today a session keeps only the user text and the reply (the last `AI_AGENT_HISTORY_TURNS`, default 6 exchanges); tool answers are not kept.
   - [ ] A: not kept; the planner asks the user or queries again (safe, no customer data held between messages)
   - [ ] B: the writer's reply (which already contains what was said) is the only memory, as today
   - [ ] C: the last tool answer of the session is kept in memory
   *Default: B, which is what happens without extra work. Say A or C only if the web chat will do many follow-ups.*
   A:Given that it stores the reponse object, with all the workflow done, it can send if the session isnt new send by default the initital message + the response. This way is more acurate and could avoid most of the confusions.

9. **What to measure for tool calls.** Per call: the tool name, the outcome kind (ok, timeout, `input`, `not_found`, `retry_later`, `source_problem`, `internal`), the duration. Never arguments or answers (Q02-7).
   - [ ] A: add these to the logs only
   - [ ] B: also to `SessionMetrics` and Langfuse (a span per tool call, with the name and the outcome, no values)
   *Default: B, so a slow or failing tool is visible next to the cost.*
   A:Default

10. **`GET /available`.** It only checks that a provider key or `OLLAMA_URL` exists. It does not say whether the Go service is reachable.
    - [ ] A: leave it as it is (it must never call anything)
    - [ ] B: add the state of the MCP servers to its answer, from the cached listing of question 5 (no new network call on the probe)
    *Default: A, because `/available` is a probe that other services call often and the contract is in the bundled wheel.*
    A:There is no need to verify mcp tools. But we can make a way that given env vars if its filled it checks X mcp. Diferent env vars per MCP

## D. Keeping it correct over time

11. **A snapshot of the tool list.** The Go service can rename a tool or change its parameters; the planner would then break silently.
    - [ ] A: a fixture holds the tool names and parameters taken from the Go docs (placeholders only); a test checks that the allowed list of question 2 matches it; the snapshot is refreshed by hand in T-01.9 from the real service
    - [ ] B: no snapshot
    *Default: A.*
    A:Default

12. **Documentation of the Go contract.** Questions 2 and 11 mean ai-agent depends on the `dynamics_microservice` MCP contract. 
    - [ ] A: a short section in `docs/api/` ("tools consumed") that names the Go document and ADR as the source, and says which tools ai-agent uses
    - [ ] B: no extra document
    *Default: A (part of T-01.8).*
    A:Default

13. **Who decides when the epic is done?** T-01.9 (the first real run) closes it.
    - [ ] A: you, after you have run it and reviewed the Langfuse traces
    - [ ] B: the acceptance criteria of the tasks are enough
    *Default: A.*
    A:Default
