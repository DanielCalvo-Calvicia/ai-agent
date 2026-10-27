> **UNMEASURED NOTES (banner added 2026-10-01).** An early, unmeasured recommendation table (model ids of several providers, some retired). The models in use are set in `config/step_models.json`; the generated tables are `gemini_models_per_step.md` and `models_per_step_budget.md`. Only `gemini-2.5-flash` and `openai/gpt-oss-120b` were run end to end.

| Phase                   | Role                              | Complexity   | Reasoning Useful | Tool Use Required | Structured Output | Budget Pick    | Balanced Pick           | Quality Pick      | Key Reason                                                                                                                           |
| ----------------------- | --------------------------------- | ------------ | ---------------- | ----------------- | ----------------- | -------------- | ----------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **1** Triage Specialist | Classify intent                   | 🟢 Low       | ❌               | ❌                | ✅                | `gpt-4.1-nano` | `gemini-2.5-flash-lite` | `gpt-4.1-mini`    | Pure classification, tiny output, called once                                                                                        |
| **2** Project Manager   | Build recursive action tree       | 🔴 High      | ✅✅             | ❌                | ✅                | `gpt-4.1`      | `o4-mini`               | `gemini-2.5-pro`  | Most critical phase — poor planning breaks all downstream phases; reasoning prevents shallow decomposition                           |
| **3** Safety Gatekeeper | Validate plan safety              | 🟢 Low       | ❌               | ❌                | ✅                | `gpt-4.1-mini` | `gemini-2.5-flash-lite` | `gpt-4.1-mini`    | Binary classification with small JSON; no reasoning needed                                                                           |
| **4** Cognitive Worker  | Execute one internal action       | 🟡–🔴 Varies | ✅               | ❌                | ✅                | `gpt-4.1`      | `o4-mini`               | `claude-sonnet-4` | Called once per action in a loop — reasoning helps for `analysis` / `generation` tasks; avoid heavyweight models for trivial actions |
| **5** MCP Operator      | Execute one tool call             | 🟡 Medium    | ❌               | ✅✅              | ✅                | `gpt-4o-mini`  | `gpt-4.1`               | `gpt-4o`          | Tool call reliability is the only metric that matters here; GPT-4o-mini has best cost/reliability ratio for tool use                 |
| **6** Data Engineer     | Normalize one output              | 🟢 Low       | ❌               | ❌                | ✅                | `gpt-4.1-nano` | `gemini-2.5-flash-lite` | `gpt-4.1-mini`    | Called once per action; pure text cleaning; cheapest phase to run                                                                    |
| **7** Draft Writer      | Synthesize all outputs into draft | 🟡 Medium    | ❌               | ❌                | ✅                | `gpt-4.1`      | `claude-haiku-4-5`     



| Phase | Recommended Model  | Why                                                          |
| ----- | ------------------ | ------------------------------------------------------------ |
| 1     | `gpt-4.1-mini`     | Fast, cheap, great at JSON classification                    |
| 2     | `o4-mini`          | Reasoning for planning, structured output, affordable        |
| 3     | `gpt-4.1-mini`     | Binary safety decision, tiny JSON                            |
| 4     | `o4-mini`          | Reasoning per action, handles complex tasks well             |
| 5     | `gpt-4o-mini`      | Best tool-calling reliability at low cost                    |
| 6     | `gpt-4.1-nano`     | Cheapest available, text normalization needs no intelligence |
| 7     | `claude-haiku-4-5` | Good writing, cheap, fast                                    |
| 8     | `claude-sonnet-4`  | Best editorial quality for final user output                 |