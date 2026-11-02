# step_defs/

One JSON declaration per step: its kind, prompt, answer pieces, `reads` and `writes` (PR-005 section 3.2). Named `step_defs` so it does not share a name with `application/steps/`, which holds the Python of the steps.

Empty until T-05.16. Until then each step is a Python file in `application/steps/` that registers itself in `application/steps/registry.py`.
