# ADR-015 — Profiles, flows and steps are three separate layers, and the client chooses the profile

**Status:** Accepted (2026-11-02, by the maintainer, after reviewing [PR-005](../proposals/PR-005-flows-steps-profiles.md)). Built in epic [T-05](../tasks/T-05_profiles-flows-steps/T-05_profiles-flows-steps.md) (closed 2026-11-04) and, for the flows and prompts, in epic [T-06](../tasks/T-06_redesign/T-06_redesign.md) (not started). It changes [ADR-003](ADR-003-one-call-per-utterance.md), [ADR-004](ADR-004-four-flows-behind-one-router.md) and part of [ADR-014](ADR-014-fallback-models-after-a-lack-of-capacity.md); each of them carries a dated note of 2026-11-04.

## Context

Today a flow is Python with a hard-coded list of steps, a "profile" is a table of models for all flows (`config/step_models.json`), the default model lives in each step, the router is two constants in code, and one message is one call that the service routes inside. The owner wants one service for several clients (the robot, a web chat, other projects) that behave differently, and wants a new step, flow or profile to be a set of files. The answers are in Q05 to Q09.

## Decision

1. Three layers, one direction: **profile -> flow -> step -> model catalog**. A profile is one flow, or one ordered list of steps, plus models, tools, prompts and the inputs it accepts. A flow is an ordered list of steps with named pause and retry rules, with no branches. A step is one job, declared in JSON.
2. **The client chooses the profile on every request**, with a token (a check against a mistake, stored as a hash). The service no longer routes: the client chains the profiles (`identification`, then the profile of the answer). A request with no profile gets `default`.
3. The result of a profile is the `Response` of its last step. The client may ask for the text only or the whole object, and may send a `Response` back as `inputs` of the next profile. A question to the user is answered with a `pause_id`.
4. The session keeps a list of `Response` objects, one per request, instead of text pairs.
5. Models: the most specific value replaces the broader one, and the ordered list is also the fallback. Tools: the narrowest limit wins. Environment variables no longer override models.
6. Everything is plain data read once at start through a port (files today; SQL, S3, LangChain services later). `assemble()` checks the whole agent at start; a wrong profile is disabled in production and stops the tests.
7. Structure first (epic T-05, golden file unchanged), redesign of the flows and prompts after (epic T-06).

## Consequences

- Brain must chain profiles; until it does, the robot has no movement and no gesture. Nothing is in production.
- The API gains `profile`, `token`, `inputs`, `return`, `pause_id`, `client` and `profile`, `output`, `pause_id`, `discarded_pause`; the `contracts` repository changes later, by the owner.
- The data policy is not built; the fields to apply it are reserved.
- Many files and paths change (stage S1); the golden file must stay identical through S1, S3 and S7.
- A token stored as a hash in a repository is a check against mistakes, not access control; business data is protected by which profile has which tools.

## As built (note of 2026-11-04, T-05.18)

Epic T-05 built decisions 1 to 6; decision 7 continues in T-06. What differs from the text above, all recorded in the notes of [PR-005](../proposals/PR-005-flows-steps-profiles.md) and of each task:

- **The flow files keep the names of the old Python flows** (`conversation`, `expression`): the `flow` field of an answer and the metrics do not change. The profiles `chat` and `gesture` name them.
- **Ten LLM steps are declarations; the answer check (phase 9) and the clarification (phase 99) stay in Python**, because the engine runs them itself and they are not steps of a flow. The code steps (`action_executor`, `motion_validator`, `gesture_builder`) are declared for their `reads` and `writes` and name their Python function.
- **The tokens in the profile files are placeholders** (64 zeros): the maintainer writes the real hashes. The first real run (T-05.11, 2026-11-03) used a token made for the run, in memory.
- **Brain and the `contracts` repository are not changed**: Brain still makes one call with no profile and gets `default`, so the robot has no movement and no gesture until Brain chains the profiles.
- **Not built, as decided:** the data policy (the fields `data.reads` and `data_allowed` are reserved and nothing reads them) and other config sources than files (the port exists).
