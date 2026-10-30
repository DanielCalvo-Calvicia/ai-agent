# Q01 — Before building the dynamics_microservice MCP tools

**Answered by the maintainer on 2026-10-27 and processed** into [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) (*Resolution*), with [Q02](Q02_after-q01.md).

Same format as the questionnaires of `dynamics_microservice`: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets** (write *where* they live, not their values). Each question says why it matters and my **default**, the answer I will assume if you do not answer.

Fills: [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) (questions 1 to 4) and the open points of epic [T-01](../../tasks/T-01_dynamics-mcp/T-01_dynamics-mcp.md). Source: the reading of `D:\Snowfactory\Programas\GO\dynamics_microservice` (`docs/api/mcp.md`, ADR-025) on 2026-10-27. The Go project is not modified by this epic.

---

## A. What the agent can do

1. **Which tools does the agent get?** The Go service offers the workflows `customer_orders`, `order_status`, `customer_card` (fixed templates: the agent gives a customer code and the service owns the table, the fields and the limits) plus `list_workflows`, `get_guidance`, `get_job_result`, `cancel_job`. With `MCP_EXPOSE_GENERIC_TOOLS=true` (its default) it also offers `list_tables`, `describe_table`, `plan_query` and `run_query`, which can read any field of any table of the catalogue. The setting is on the Go side, not in ai-agent.
   - [X] A: only the workflows and their helpers (the Go service is started with `MCP_EXPOSE_GENERIC_TOOLS=false`)
   - [ ] B: also the generic query tools
   *Default: A. The planner cannot build free queries and the data it can reach is small and validated.*
   A:Default

2. **Who may ask about customers and orders?** The robot talks to whoever is in front of it. Today ai-agent has no notion of who the speaker is beyond `user_id` and `username`, and the Go service has no authentication, so anyone who talks to the robot could ask for the orders of any customer.
   - [ ] A: anyone who talks to the robot (no restriction)
   - [ ] B: only some users (say how ai-agent knows them: the `user_id` of Brain, a list, ...)
   - [ ] C: LATER (not decided; keep it for a trusted demo only)
   *Default: C, and the first version is documented as for a trusted environment only.*
   A:Default, there will be multiple users

3. **May business data be spoken aloud?** The reply is spoken by the robot, in a room. Order numbers, amounts, customer names and balances are business data.
   - [ ] A: yes, as asked
   - [ ] B: yes, but short (a count, a status, a total, never a list of names)
   - [ ] C: no amounts or personal data; only counts and statuses
   *Default: B.*
   A:A, because this agent will be used across multiple other project that arent the robot, the robot is just one of them

4. **Which language do the replies use?** Users may say "pedidos del cliente X" or "orders of customer X". The Go service matches synonyms in English and Spanish; the prompts of ai-agent are English.
   - [ ] A: reply in the language of the user
   - [ ] B: always Spanish
   - [ ] C: always English
   *Default: A.*
   A:Default

## B. Where the data goes

5. **Customer and order data goes to third parties.** Every call sends the answer of the tool to the LLM provider of the step that reads it (the data engineer, the writer, the editor), and when the Langfuse keys are set, Langfuse stores the prompts and answers (the user's text included).
   - [ ] A: accept it for these tools
   - [ ] B: use a Langfuse project you trust with it
   - [ ] C: leave the Langfuse keys empty for runs that use these tools
   - Also say whether **any** of the providers in use may not receive customer data (for example, a provider outside the EU). *Name the providers, never keys.*
   *Default: C for the first runs, until you decide.*
   A:For now, giving that is a prototype i prefer B ,then i will change the stored data with placeholders

6. **Which models may read this data?** The configured profile (`budget50_groq`) was never run as a combination, and no real call has been made since the four-flow redesign. The steps that will see the tool answer are the MCP operator, the data engineer, the draft writer and the editor.
   - [ ] A: the same models as today
   - [ ] B: a specific profile or model for these steps (write it)
   *Default: A for the scripted tests; the real run (question 13) picks the profile with you.*
   A:It will be Claude

## C. How ai-agent reaches the service

7. **Where does `dynamics_microservice` run, and how does ai-agent connect?** The endpoint is `POST http://<host>:<port>/mcp` (Streamable HTTP, stateless, JSON answers). The Go docs name four topologies: client -> AWS Lambda -> VPC -> EC2 -> Kubernetes -> service; local; public server -> Kubernetes; public server -> service. **Do not write a real host here**: write the kind of place and where the value will live (the variable `DYNAMICS_MCP_URL` in `.env`).
   - Where does it run for development (on this machine, in the cluster, ...)?
   - Where does it run for the robot (the same machine as ai-agent, the cluster, behind the Lambda)?
   - If it is behind the Lambda: does the Lambda forward `POST /mcp` and the headers? (API Gateway cuts at 29 s.)
   *Default: development on this machine at its default port, the robot's place `LATER`; no Lambda in the path.*
   A: The development enviroment is mixed. At the begginign dynamics_microservice will be inside a kuebrnetes, outside the network of the ai-agent, after all this works, the agent will be set inside the kubernetes enviroment and will be used by a web chat.

8. **Which Business Central environment and company?** Every tool takes optional `environment` and `company`; when they are left out the Go service uses `MCP_ENVIRONMENT` and `MCP_COMPANY` (and if empty, the first configured). The robot may or may not let the user choose.
   - [ ] A: always the defaults of the Go service; the user cannot name them
   - [ ] B: the user may name them and the planner passes them on
   - Is the default a sandbox or production? *Never write names or codes of environments or companies; say only "sandbox" or "production".*
   *Default: A, against the sandbox.*
   A:Default

9. **Authentication.** The Go endpoint has none today; a common middleware for all Snow Factory projects is planned (Go project, Q33-8). ai-agent has none either (Brain calls it inside the workspace). OK to build without any now?
   - [ ] A: yes, build without authentication and document it as a known limit
   - [ ] B: no, wait until the common middleware exists
   *Default: A.*
   A:Default

## D. How it behaves

10. **Slow queries.** The Go service waits up to 20 s for a query; if it is not done it answers `status: running` with a `job_id`, and the agent must call `get_job_result` later. The robot is a voice interface: a long silence is bad.
    - [ ] A: the planner follows up with `get_job_result` (a bounded number of times) and then answers
    - [ ] B: the robot says "it is still running, ask me again in a moment" and stops
    - What is the longest the user should wait for an answer (seconds)? The call limit defaults to 30 s (T-01.4); with A the total can be longer.
    *Default: A, with at most one follow-up, and a total wait you give here (default 60 s).*
    A:Default

11. **Errors.** The service answers `error (input|not_found|retry_later|source_problem|internal)`. What should the robot say?
    - [ ] A: a short, honest sentence per kind (not found / not available now / it failed), never repeating a code the user did not give
    - [ ] B: the same sentence for every failure
    *Default: A.*
    A:Default

12. **Should a tool call ask for confirmation?** The tools are read-only, so the special flow's safety gate does not need to block them. Do you want it to confirm before querying customer data?
    - [ ] A: no confirmation (read-only)
    - [ ] B: yes, ask "do you want me to look up customer X?" every time
    *Default: A.*
    A:Default

## E. Other tools and how it is built

13. **The "different tools" of the other projects.** The epic builds the Streamable HTTP transport once, so any server that speaks it needs only a JSON file in `mcps/`. List the tool projects you want next (the name and the folder are enough) and say what transport each speaks, if you know it: Streamable HTTP, SSE, or stdio (stdio is not supported and is not in this epic).
    *Default: only `dynamics_microservice` now; the others are new epics.*
    A:Default

14. **The first real run.** It costs money and reads real Business Central data (read-only). Who runs it and when?
    - [ ] A: you run it, with the sandbox and a test customer you choose (write only "a test customer", never the code); the assistant prepares the command and says what to look at
    - [ ] B: the assistant runs it after you say go
    - Which providers have keys in your `.env` for it (names only)? Is a budget limit for the run needed (an amount)?
    *Default: A, with `gemini-2.5-flash` on every step (the only model ever run end to end) and no Langfuse.*
    A:A, but will be a claude llm, that is on enterprise mode

15. **The test environment.** The `windows` venv is not in this checkout, so the suite cannot be run here. Who recreates it, and with which Python (the folder says 3.14 on Windows, 3.12+ elsewhere)?
    - [ ] A: you recreate it
    - [ ] B: the assistant recreates it with the interpreter you name (write it)
    *Default: B, with the newest Python of the machine that satisfies `requirements.txt`; it will ask before installing.*
    A:Default

16. **Git flow.** One pull request per task (T-01.2, T-01.4, ...) or one for the whole epic? Who commits and pushes (the project rule is: never unless asked)?
    - [ ] A: one pull request per task
    - [ ] B: one pull request for the epic
    *Default: A, committed and pushed only when you ask.*
    A:Default
