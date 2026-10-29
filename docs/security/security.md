# Security

## Secrets

- `.env` holds many provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`, `LANGFUSE_*`; `GITHUB_PAT` is no longer used). It is never committed. Copy `.env.example` to `.env`.
- Never read the values out, print them or copy them into code, tests, fixtures, documents or memory. Documents name variables only.
- The process environment wins over `.env` (`override=False`).

## What the service can do

- It **never controls hardware**: it only returns `directives`; Brain acts on them (see [ADR-002](../decisions/ADR-002-agent-decides-brain-acts.md)).
- Every movement it returns passes the motion validator (plain code, no LLM): valid arm and direction, degrees within limits, at most 20 movements and 3600 degrees in total. One bad movement refuses the whole sequence, and the refusal is always said to the user. A gesture that the validator refuses is dropped.
- The special flow has a **safety gate** (phase 3) that fills `safety_and_validation` and may require a confirmation; an MCP action is blocked while a confirmation is pending. A tool that only reads data never asks for one.
- **Business Central is read-only for this service.** ai-agent only calls the tools of `allowed_tools` in `mcps/dynamics_microservice.json` (the workflows and their helpers); every other tool the server lists is hidden and cannot be called, and the Go service is started without its generic tools. No environment or company is ever sent. A tool result is data: the prompts say a sentence inside it is never an instruction.

## Exposure

- No authentication and no CORS in this service: it is meant to be reached by Brain inside the workspace only. Do not expose port `7998` outside it.
- Sessions live in process memory and are not tied to a caller identity beyond `user_id` (3 to 128 characters).
- **`dynamics_microservice` has no authentication either**: its endpoint is open and ai-agent reaches it by a **public IP and port over plain HTTP**, set only in `DYNAMICS_MCP_URL` (never in git). Anyone who can reach that address can read what the service exposes. A Cognito identity service is planned; **who may see which customer is decided by a layer above ai-agent**, not here. Some requests will carry sensitive data (customer names, orders), but most are capped by the Go service, which forces what it returns. When ai-agent moves inside the Kubernetes network the address becomes a cluster service name.

## Data sent to third parties

- Every LLM call sends the user's text, the recent history (`AI_AGENT_HISTORY_TURNS`) and the prompts to the provider chosen for that step. For a request about Business Central that **includes the customer and order data the tools returned**: it goes to the provider of the step that reads it (planned: Claude, through an Anthropic key of the enterprise organisation; the data policy of that account is `UNKNOWN`, so the first real run uses a test customer with no real personal data). **Since 2026-10-29 the personal columns of a tool answer are hidden before any model sees them** (`infrastructure/outbound/mcp/masking.py`, `AI_AGENT_MASK_PERSONAL_DATA`, default on): a cell under a header that names a customer, an e-mail, a phone, an address, a contact or a tax or bank number becomes `[hidden]`; customer and order codes, dates, amounts and states are kept. It matches headers by name, so a new tool with a differently named personal column is not covered until the list is extended, and the user's own words and the customer code still reach the provider.
- **Langfuse**, when its keys are set, receives the user's text and the prompts and answers of every call, not only metadata. Use a project you trust (see [monitoring](../operations/monitoring.md)). For the Dynamics tools this is accepted **on purpose in the prototype phase**, so the maintainer can see the data; the project must be trusted for customer data, and later the data moves to a more secure store on AWS or SQL. To keep it out, leave the Langfuse keys empty for runs that use these tools.
- MCP tool servers receive the tool arguments the model builds, and the trace headers.
- The libraries under the MCP client (`httpx`, `httpcore`, `mcp.client`) would log the server URL and, at DEBUG, the tool arguments: they are kept at WARNING (see [monitoring](../operations/monitoring.md)). A deployment that raises their level itself reopens that.
- The logs, `SessionMetrics` and the Langfuse span of a tool call hold only the tool name, the outcome, the duration and the number of tries: never the arguments or the answer. (The generation of the step that uses the tool still carries its prompt and answer, with whatever the tool returned: see Langfuse above.)
- **Google free tier (the default models, ADR-012).** Google says the content of free-tier requests is used to improve its products; paid-tier content generally is not. The default models are Google's, so with a free key the user's text, the history, the prompts and, in the special flow, the answers of Business Central tools go to Google under those terms. Use the free tier with test data; for real customer data use a billed key (about 175 EUR per 1,000 big-plan messages at paid prices) or another provider. Google does not publish the free-tier rate limits.
- **Anthropic (the Claude profiles, ADR-013; not active by default).** With a Claude model the user's text, the history, the prompts and, in the special flow, the answers of Business Central tools go to Anthropic through its OpenAI-compatible endpoint, with a strict schema attached to every call. Anthropic documents that endpoint as a layer for testing, not for production. Nothing goes to Anthropic unless `ANTHROPIC_API_KEY` is set and a profile (or a step) names a Claude model.

## Dependencies

- `contracts` comes from the bundled wheel in `vendor/` (refresh with `contracts/scripts/bundle.py`); `shared-logging` is a sibling package. Nothing is downloaded at run time.

## Open points

- Authentication between Brain and ai-agent: UNKNOWN (not decided in the repository).
- Authentication of the clients of ai-agent in general (a web chat is planned next to the robot) and of the Go service: planned (Cognito), not built.
