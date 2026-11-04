# T-06 — Redesign: the new flows, steps, prompts and profiles

| | |
|---|---|
| Status | in-progress (T-06.1 done 2026-11-04; T-06.3 closed with no change; T-06.2 done; next: T-06.4) |
| Kind | epic |
| Parent | project |
| Depends on | T-05 |
| Blocks | — |

> Source: PR-005 section 11 and Q08-4: structure first (T-05, the golden file does not change), redesign after, so a bad answer has one obvious cause. The maintainer wrote in Q07-4 that "all flows and steps will need refinement, the prompts also" and that the plan must be very concrete.

## Goal

Redo the flows, the steps, the prompts and the profiles on the structure T-05 built, **one change at a time, each compared with the answers T-05 gave**.

## What exists and what changes

| After T-05 | After T-06 |
|---|---|
| The seven profiles reproduce today's flows (plus the triage in `special` and `dynamics`) | The flows the maintainer specifies in T-06.1 (the table of Q08-3 is the starting point, not the end) |
| The prompts are the ones of 2026-11-02 | Refined prompts, per step and per profile where they differ (for example `robot_triage`, Q09-8) |
| No step for a flow with no planner | New steps, as many as T-06.1 asks (for example a tool caller: Q07-4 A) |
| Profiles `proven`, `claude_*` as placeholders | The models of each profile chosen with the real-run results |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-06.1 Specification of the new flows](T-06.1_specification.md) | decision | done (2026-11-04) |
| 2 | [T-06.2 The fixed set of messages](T-06.2_message-set.md) | test | done (2026-11-04, mock only) |
| 3 | [T-06.3 New steps](T-06.3_new-steps.md) | code | done, no change (T-06.1 asks for no new step) |
| 4 | [T-06.4 Refine the prompts, one step at a time](T-06.4_refine-prompts.md) | code | todo |
| 5 | [T-06.5 The new flows and profiles](T-06.5_new-flows-and-profiles.md) | code | todo |
| 6 | [T-06.6 Real run and comparison](T-06.6_real-run-and-comparison.md) | manual | todo |
| 7 | [T-06.7 Documentation](T-06.7_documentation.md) | docs | todo |

## Exit criteria

Every profile of T-06.1 runs on mocks and on the real models; each prompt change is explained by a comparison of the fixed set of messages against T-05's answers; the maintainer read the prompts; the documents are true.

## Rules that bind every task of this epic

- One prompt, one step or one flow per change; run the fixed set before and after; keep both outputs in `tests/output/`. A change that makes an answer worse is reverted, not tuned in place.
- A change to a prompt, schema, model or message format changes the golden file: read the diff first, then regenerate on purpose.
- A prompt keeps matching its schema (`docs/rules/schemas-and-prompts.md`, section 4); the Claude sanitizer limits (ADR-013) are checked by `assemble()`.
- No real call without asking the maintainer. Commit and push only when asked. The baseline of the [tasks README](../README.md) section 3.
