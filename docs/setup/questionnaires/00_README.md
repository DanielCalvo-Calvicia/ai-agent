# Questionnaires — how to answer

Same format as `dynamics_microservice/docs/setup/questionnaires`. Answer in Spanish or English; the assistant translates to the language of the docs.

**Answer format**

- Write after `A:` on each question. For multiple choice, mark the option with `[x]` and add detail after `A:` if needed.
- Don't know -> `UNKNOWN`. Doesn't apply -> `NOT APPLICABLE`. Decide later -> `LATER`.
- Never write passwords, tokens, hosts of a private network or real customer data. Write *where* they live, not their values.
- Each question says why it matters and the **default**: the answer the assistant assumes if you do not answer.

When you finish a questionnaire, say which one: the assistant writes the answers into the task *Resolution*, the ADR and the documents it changes, and marks the row below as processed.

| Q | State | What it decides |
|---|---|---|
| [Q01](Q01_dynamics-mcp.md) | answered and processed 2026-10-27 (T-01.1) | before building epic T-01 (the `dynamics_microservice` MCP tools): which tools, where the data goes, how ai-agent reaches the service, who may ask, how it sounds, how it is tested; fills [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) |
| [Q10](Q10_mcp-job-follow-up.md) | answered and processed 2026-11-11 (T-07.1, ADR-018 accepted, new task T-07.10) | how a job answer of an MCP server is followed up: which servers and who can change them, where the follow-up lives, how long it waits, what happens when the budget ends, an unknown shape, two jobs in one answer, `custom`, the shipment tools, the roll-out; fills [T-07.1](../../tasks/T-07_mcp-job-follow-up/T-07.1_decisions.md) and decides [ADR-018](../../decisions/ADR-018-mcp-job-follow-up-per-server.md) |
| [Q09](Q09_profiles-per-message.md) | answered and processed 2026-11-02 into [PR-005](../../proposals/PR-005-flows-steps-profiles.md) and [ADR-015](../../decisions/ADR-015-profiles-flows-steps.md) (proposed) | what a profile on every message changes: how the second call gets what the triage found, what a profile answers with, which profile receives the answer to a question, which calls write to the history, what `default` and `special` may reach, what T-05 reproduces, shared profiles, the first acceptance run |
| [Q08](Q08_profiles-third-follow-up.md) | answered and processed 2026-11-02 into PR-005 (asked 2026-10-30) | the last blockers before PR-005 is rewritten: who picks the flow when the robot has several profiles, the table of steps per flow, structure first and redesign after, the closed catalog of state fields, the role of the token, headers before the contract changes |
| [Q07](Q07_profiles-second-follow-up.md) | answered and processed 2026-11-02 into PR-005 (asked 2026-10-30) | the points where the answers of Q06 pull in different directions: branching inside one flow, conditions, the flows of the new design, tools without a planner, how far JSON goes for steps, the order of models, the token of a profile, what a request with no profile gets, the data policy, other sources for the files, what a wrong profile does at start, the layout and the layers |
| [Q06](Q06_profiles-follow-up.md) | answered and processed 2026-11-02 into PR-005 (asked 2026-10-30) | what the answers of Q05 changed or left open: a profile chosen by the client on each session, flows or steps inside a profile, MCP scoping per level, prompts per profile, declarative steps, the API contract change, files and deployment, metrics, the order of stages |
| [Q05](Q05_flows-steps-profiles.md) | answered and processed 2026-11-02 into PR-005 (asked 2026-10-30) | before [PR-005](../../proposals/PR-005-flows-steps-profiles.md) is accepted: what a profile is for you, one profile or several at once, what a profile may change (models, steps, prompts), data and cost rules per profile, when the configuration may change, testing, order of work and scope |
| [Q04](Q04_last-clarifications.md) | answered and processed 2026-10-27 (T-01.1, new tasks T-01.10 to T-01.12) | the last questions before the build: what a session keeps between messages (Q03-8), the per-MCP check and where its result goes (Q03-10), the details of the tool-call cap, the Claude model id, the branch and pull request flow, committing the documents, recreating the venv; Q03 and Q04 are processed together |
| [Q03](Q03_refinement-and-good-practices.md) | answered and processed 2026-10-27 (T-01.1 and the tasks) | refinement and good practices: tool results as untrusted data, an allowed-tools list, a cap on tool calls, retries and timeouts, a down Go service, total latency, caching, memory of follow-ups, metrics, `/available`, a snapshot of the tool contract |
| [Q02](Q02_after-q01.md) | answered and processed 2026-10-27 (T-01.1) | what the answers of Q01 left open: who may see which customers, the web chat as a client, how the Go service is reached now and later, masking and logs, which Claude models and account, the reply format and size, the order of the first pull requests |
