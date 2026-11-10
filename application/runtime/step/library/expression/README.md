# application/runtime/step/library/expression/

Code for the `gesture` profile (flow file `flows/expression.json`).

| File | Contents |
|---|---|
| `gesture_builder.py` | Phase 31, **plain code, no LLM**. Builds the arm gesture that goes with a spoken reply from the emotion the `emotion_reader` found: random movements shaped by the emotion (`domain/operations/gesture.py`), with `pause_seconds` between them about as long as the speech, every arm back where it started. The motion validator checks the result as a safety net; a gesture it refuses is dropped, never sent (the reply is spoken anyway). |

The random generator comes from `support/expression_settings.py` (`AI_AGENT_EXPRESSION_SEED` makes it repeatable; `AI_AGENT_SPEECH_CHARS_PER_SECOND` sizes the speech). Brain asks the `gesture` profile with the reply and starts the gesture when the robot starts to speak; the service adds none to a reply by itself.
