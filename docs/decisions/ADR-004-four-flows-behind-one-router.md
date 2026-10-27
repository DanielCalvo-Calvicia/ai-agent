# ADR-004 — Four flows behind one router

**Status:** Accepted (2026-10-05); implemented in `811764f` (2026-10-07) and merged to `feature` in PR #3 (2026-10-27)

## Context

One pipeline answered everything, then two flows were split (PR-002). A fast-path heuristic and `robot_context` tried to guess what a message was.

## Decision

Four flows in one service and one venv: `identification` (triage), `conversation` (draft writer, editor), `special` (project manager, safety gate, action executor, draft writer, editor) and `movement` (motion planner, motion validator). Every message goes through identification; `task_category.domain` then picks ONE flow in `flows/router.py` (`FLOW_BY_DOMAIN`): `communication` -> conversation, `movement` -> movement, anything else -> special.

- The flows never call each other; only the router hands the identification state to the next flow (`take_over`).
- A flow that asked the user a question is resumed by the next message (`PausedRun.flow`).
- Every flow runs on the same engine (`Pipeline`), which knows no particular flow.
- The fast-path heuristic and `robot_context` were removed.

## Consequences

- Positive: nothing is classified twice; a new flow is a file, its phases and one line in the registry and the router.
- Negative: a message that mixes a reply and a movement goes to one flow only; a wrong `domain` sends the message to the wrong flow.
