# tests/manual

Scripts that are **not collected by pytest**. Most call real LLMs or the real Dynamics service and cost money: ask the maintainer first. The one that matters for epic T-06 is the fixed set of messages.

## The fixed set of messages (T-06.2)

`profile_messages.json` is the yardstick every prompt, step, flow or model change is judged by (Q08-5 A: the judge is a person; there is no automatic judge). `scripts/run_profile.py` sends it to a profile and saves the answers.

Each message has:

| Field | Meaning |
|---|---|
| `id`, `message` | The name of the message and its text. Sandbox customer codes only (`CL-1001`), never a real customer. |
| `points` | What a good answer must contain: one short, checkable line each. They become boxes to tick. |
| `points_for` | Points that **replace** `points` for one profile that answers something else: `identification` answers a classification, `gesture` an emotion, `movement` answers a non-movement message with "I only move my arms". |
| `profiles` | The profiles the message makes sense for (no key: all of them). |
| `then` | The user's answer to the question the message makes the profile ask (`movement_ask`, `ask_family`, `dynamics_ask`): sent as the next message of the **same** run, which is the paused-run path (the `answer_checker` judges it and the step that asked runs again). It has its own `points`. If the profile did not ask, the report says so and the answer is not sent. |

The set: a greeting in English and in Spanish, a question with no tool, a Spanish explanation, something the robot cannot do (`impossible`), a request for a document (`document`: it cannot make files), a plan, a movement in English and in Spanish, a movement with a missing detail, a plan that must ask the user (`ask_family`), a Dynamics question and one that must ask for the customer code.

## Running it

```bash
python scripts/run_profile.py movement --mock                 # a scripted model: no cost, no keys, checks the script and the report
python scripts/run_profile.py special --label before          # REAL models: asks first, costs money; the Dynamics messages need the service
python scripts/run_profile.py special --label after --yes     # does not ask (only when the maintainer said so)
```

- Use `--label before` and `--label after` around a change (T-06 rule: one change at a time, both reports kept). The report is `tests/output/profile_run_<profile>_<date>[_<label>].md`.
- A `--mock` run is not a real run: its report says so, and **it still writes `tested: <date>` in the profile file** (the script marks a profile when every message got an answer). Run it with `--root <copy>` or revert `profiles/<name>.json` afterwards.
- A real run needs the keys of `.env` (their values are never printed) and, for the Dynamics messages, the service running.

## Reading the result

1. Open the report. For each message, read the answer and tick (`[x]`) every point it meets.
2. Compare with the report of the run before, message by message: **better, the same or worse**, with the tokens and calls of the header and of each message.
3. Worse: the change is reverted, not tuned in place. Write what changed in the Notes of the task.
4. A profile that answers with no text (`identification`) shows what the triage decided in a `**Classified as:**` line (domain, type, complexity, next step, the questions it asks). A model varies between runs: before judging a message that looks worse, run that one message several times, before and after (`--messages <file>` with only that message).

The other scripts here (`full_flow_real_llm.py`, `budget_run.py`, `chat_session.py`, ...) were written before the redesign and were not re-run after it.
