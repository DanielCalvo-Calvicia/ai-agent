# flows/

One JSON file per flow: an ordered list of steps with named pause and retry rules (PR-005 section 3.3). No branches and no sub-flows.

Filled in T-05.12: `identification`, `conversation`, `special`, `movement` and `expression` (the names the Python flows had; a profile's `flow` names one). Keys:

| Key | Meaning |
|---|---|
| `steps` | in order; a name, or `{step, pause_if, retry_on_status}`. `pause_if` is a condition of `application/steps/conditions.py`; `retry_on_status` runs the step again while its answer says retry or error |
| `on_pause`, `on_resume` | the hooks of `application/steps/hooks.py` (`user_clarification`, `answer_checker`); only a flow with a step that can ask carries them |
| `result_from` | the step whose result is the result of the flow (`hooks.py` builds it: the text, the movements or the gesture) |

A step, a condition and a hook are names a developer writes in Python; a flow cannot invent one. `python scripts/check_agent.py` checks every file.
