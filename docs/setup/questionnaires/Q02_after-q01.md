# Q02 — What the answers of Q01 left open

**Answered by the maintainer on 2026-10-27 and processed** into [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) (*Resolution*). Question 12 (no row limit in ai-agent) replaced the default of 10 rows; the Go service still caps at 500 rows and 64 KB.

Same format as Q01: write your answer after `A:`; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid; **never write secrets** or real hosts (write the kind of place and where the value lives). Each question says why it matters and my **default**, the answer I will assume if you do not answer.

Previous questionnaire: [Q01](Q01_dynamics-mcp.md) (answered 2026-10-27; questions 1, 4, 8, 9, 10, 11, 12, 13, 15 and 16 took the default). Fills: [T-01.1](../../tasks/T-01_dynamics-mcp/T-01.1_decisions.md) and the tasks named in each question.

What Q01 told me that changes the picture: ai-agent is not only the robot's mind. It will also serve **other projects**, first from **outside** the Kubernetes network where `dynamics_microservice` runs, later from **inside** it behind a **web chat**, with **several users**, and with **Claude** (enterprise) as the model.

---

## A. Users and access

1. **Who may see which customers?** Q02 of Q01 said "there will be multiple users" but kept the default "trusted demo". With a web chat in front, any user could ask for the orders of any customer. Where is that decided?
   - [ ] A: out of scope for this epic: the web chat or another layer controls access; ai-agent stays open and the limit is documented (known limit, in `security/security.md`)
   - [ ] B: ai-agent restricts by `user_id` (say the rule or where the list lives)
   - [ ] C: Business Central's own permissions should decide (needs a per-user identity that the Go service does not receive today; this would be a change in the Go project, not in this epic)
   *Default: A.*
   A:Default, the layer of verification will come from above. Later on will have a microservice of cognito to verify identities

2. **Who calls ai-agent from the web chat, and with what?** The web chat will call `POST /session/message`. That answer carries `directives` and `flow` fields meant for Brain, and the request has `speak_movements`.
   - [ ] A: the same API for every client; the web chat ignores what it does not need
   - [ ] B: a way for a client to say it is not a robot, so ai-agent does not plan movements or gestures for it (a new request field and a change in the contracts wheel; a separate epic)
   *Default: A for this epic; B is written down as a later task.*
   A:Default, the agent doesnt care if its the robot or another client, just acts.

## B. How ai-agent reaches the Go service

3. **How does your machine reach `dynamics_microservice` in Kubernetes today?** It runs outside the network of ai-agent. Write the kind of path, never the address.
   - [ ] A: VPN into the network
   - [ ] B: directly to a port the node exposes (NodePort)
   - [ ] C: through the AWS Lambda (it must forward `POST /mcp`; API Gateway cuts at 29 s)
   - [ ] D: other (say which)
   *Default: B, from inside a network that already reaches the node.*
   A:Now the dynamics_microservice is open, so there is no problem with reaching it with a public ip and port, must be configured via env vars, so its protected

4. **Is HTTPS needed for the first stage?** The Go endpoint has no authentication and the Go docs say an exposed `/mcp` needs HTTPS and a protection. If the path is private (VPN or the same network), plain HTTP may be accepted for now.
   - [ ] A: plain HTTP over the private path is accepted for the first stage
   - [ ] B: HTTPS is required (then the client must trust the certificate; say how it is issued)
   *Default: A, written in `security/security.md` as a known limit with the date.*
   A:Default

5. **When ai-agent moves inside the Kubernetes network, which URL does it use?** It changes only the value of `DYNAMICS_MCP_URL` (a service name of the cluster). Is it a separate task of this epic, or only a documented step?
   - [ ] A: only a documented step in `deployment/deployment.md` (the delivery of ai-agent is outside this repository)
   - [ ] B: a task of this epic
   *Default: A.*
   A:Default

## C. Data and logging

6. **Masking customer data before Langfuse.** Q01 question 5 chose a trusted Langfuse project (B) and said "then I will change the stored data with placeholders". Does that mean you will do it yourself later, or should this epic add masking of customer data (codes, names, amounts) in what the Langfuse reporter stores?
   - [ ] A: not in this epic; a known limit, you decide later
   - [ ] B: in this epic: a new task (`infrastructure/outbound/usage/langfuse.py`) that masks tool answers and, optionally, the user text. *Say which fields are sensitive: for example customer codes and names, order numbers, amounts.*
   *Default: A.*
   A:Default. What i mean is that on the prototype phase i would like to see on langfuse the data, later on will be stored on a more secure store on AWS or SQL

7. **Logs.** ai-agent logs through `shared_logging`. Today it logs the failure reasons. The Go service never logs input values. Should ai-agent also never log tool arguments or tool answers (a customer code can be in the arguments)?
   - [ ] A: never log tool arguments or answers; log only the tool name, the outcome and the duration
   - [ ] B: log arguments, but not answers
   *Default: A.*
   A:Default

## D. Claude as the model

8. **Which Claude model for which step?** The code catalog has Claude ids up to `claude-4-6-opus-latest` and `claude-4-6-sonnet-latest`; a commented row for `claude-opus-4-5`; the models of the newest family are not in the catalog. Steps that see the tool answer: `mcp_operator` (5), `data_engineer` (6), `draft_writer` (7), `editor_in_chief` (8); also `project_manager` (2) chooses the tool, and triage (1) routes. A cheaper, faster model for routing and a stronger one for planning is the usual split.
   - Write a model id for each step, or a profile ("all Sonnet", "Haiku for 1, 7, 8 and Sonnet for the rest"). If the id is not in `model_catalog.py`, adding the row is part of the work (a small task in T-01.3).
   *Default: the same Sonnet model for every step of this flow, so the first real run is simple; tuned after it.*
   A:Default

9. **How is the enterprise account reached?** Only the native Anthropic route is wired (`ANTHROPIC_API_KEY`, `ai_sdk`).
   - [ ] A: Anthropic's API with a key of the enterprise organisation (variable `ANTHROPIC_API_KEY`, never written here)
   - [ ] B: through a cloud provider (Bedrock, Vertex...): a new provider route, a new task
   - [ ] C: UNKNOWN (ask whoever manages the account)
   *Default: A.*
   A:Default

10. **Does the enterprise data policy allow customer data to be sent?** It may settle Q01 question 5 for the model providers (not for Langfuse). Say "yes", "no" or "UNKNOWN" and who confirms it. If `UNKNOWN`, the first real run uses a test customer with no real personal data.
    *Default: UNKNOWN, and the first real run uses a test customer.*
    A:Default, but yes, some request will need to send sensitive information, but most of it will be caped on the dynamics_microservice, so it will be forced to only recieve X data

## E. The reply for a web chat

11. **Reply format.** The reply today is plain speakable text (the robot reads it). You said data may be shown as asked (Q01 question 3 A) because other projects use the agent. For a web chat:
    - [ ] A: plain text only (as today); a list of orders is written as short sentences or lines of text
    - [ ] B: allow simple Markdown (lists, a small table) when the answer has several rows
    - [ ] C: the client decides (a new request field; a later task, with question 2 B)
    *Default: A, so the same answer works for the robot and the chat.*
    A:Default

12. **How many rows may the reply carry?** The Go service returns up to 500 rows (about 55 KB). The writer sees all of them. A reply with 500 lines is useless.
    - How many items should the reply list at most (for example 10), and what should it say about the rest ("and 104 more")? 
    *Default: at most 10 rows listed, then the total and "ask me for more detail".*
    A:There are calls that will send multiple rows, for now there is no limit

13. **Gestures for non-robot clients.** `AI_AGENT_EXPRESSION` is on by default and costs one extra model call per reply. For the web chat the gesture is ignored.
    - [ ] A: leave it as it is (a deployment sets `AI_AGENT_EXPRESSION=0` where no robot is connected)
    - [ ] B: default it to off in the `.env.example` of this project
    *Default: A (no change in this epic).*
    A:Default, the mixture between the robot and the generic client needs refinement

## F. Order of the work

14. **Start order.** T-01.2 (the Streamable HTTP transport) and T-01.4 (the timeouts) need no answer. After this questionnaire the rest can follow. Do you want the first pull request to be T-01.2 and T-01.4 together, or each alone?
    - [ ] A: T-01.2 alone, then T-01.4 (Q01 question 16 A, one per task)
    - [ ] B: T-01.2 and T-01.4 together, because the timeout only makes sense with the new transport
    *Default: A.*
    A:Default
