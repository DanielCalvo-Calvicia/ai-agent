# Security

## Secrets

- `.env` holds many provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`, `GITHUB_PAT`, `LANGFUSE_*`). It is never committed. Copy `.env.example` to `.env`.
- Never read the values out, print them or copy them into code, tests, fixtures, documents or memory. Documents name variables only.
- The process environment wins over `.env` (`override=False`).

## What the service can do

- It **never controls hardware**: it only returns `directives`; Brain acts on them (see [ADR-002](../decisions/ADR-002-agent-decides-brain-acts.md)).
- Every movement it returns passes the motion validator (plain code, no LLM): valid arm and direction, degrees within limits, at most 20 movements and 3600 degrees in total. One bad movement refuses the whole sequence, and the refusal is always said to the user. A gesture that the validator refuses is dropped.
- The special flow has a **safety gate** (phase 3) that fills `safety_and_validation` and may require a confirmation; an MCP action is blocked while a confirmation is pending.

## Exposure

- No authentication and no CORS in this service: it is meant to be reached by Brain inside the workspace only. Do not expose port `7998` outside it.
- Sessions live in process memory and are not tied to a caller identity beyond `user_id` (3 to 128 characters).

## Data sent to third parties

- Every LLM call sends the user's text, the recent history (`AI_AGENT_HISTORY_TURNS`) and the prompts to the provider chosen for that step.
- **Langfuse**, when its keys are set, receives the user's text and the prompts and answers of every call, not only metadata. Use a project you trust (see [monitoring](../operations/monitoring.md)).
- MCP tool servers receive the tool arguments the model builds, and the trace headers.

## Dependencies

- `contracts` comes from the bundled wheel in `vendor/` (refresh with `contracts/scripts/bundle.py`); `shared-logging` is a sibling package. Nothing is downloaded at run time.

## Open points

- Authentication between Brain and ai-agent: UNKNOWN (not decided in the repository).
