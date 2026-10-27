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
| [Q04](Q04_last-clarifications.md) | answered and processed 2026-10-27 (T-01.1, new tasks T-01.10 to T-01.12) | the last questions before the build: what a session keeps between messages (Q03-8), the per-MCP check and where its result goes (Q03-10), the details of the tool-call cap, the Claude model id, the branch and pull request flow, committing the documents, recreating the venv; Q03 and Q04 are processed together |
| [Q03](Q03_refinement-and-good-practices.md) | answered and processed 2026-10-27 (T-01.1 and the tasks) | refinement and good practices: tool results as untrusted data, an allowed-tools list, a cap on tool calls, retries and timeouts, a down Go service, total latency, caching, memory of follow-ups, metrics, `/available`, a snapshot of the tool contract |
| [Q02](Q02_after-q01.md) | answered and processed 2026-10-27 (T-01.1) | what the answers of Q01 left open: who may see which customers, the web chat as a client, how the Go service is reached now and later, masking and logs, which Claude models and account, the reply format and size, the order of the first pull requests |
