# application/runtime/step/library/movement/

Code for the `movement` flow (and the safety net of `gesture`).

| File | Contents |
|---|---|
| `motion_validator.py` | Phase 21, **plain code, no LLM**. Checks the sequence the motion planner wrote: at most 20 movements, each at most 360 degrees, at most 3600 degrees in total; known arm and direction; a real number of degrees; not zero; no contradictory sign and direction. **One bad movement refuses the whole sequence** (half a choreography is never sent), and the refusal is a sentence the robot can say aloud. Its limits are constants at the top of the file. |

The validator is cheap and always gives the same answer. The `gesture_builder` (`../expression/`) reuses it. The `movement` flow's result builder says a refusal always, and the planner's line only when `speak_movements` is on.
