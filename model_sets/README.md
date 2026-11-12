# model_sets/

One JSON file per **model set**: a named table that says which LLM answers each step. A profile picks one by name (`"models": "claude_mixed"`) at any level (PR-005 section 5). Every entry is an **ordered list**: the first model answers, the next ones are tried **only when the first is out of capacity** (429, 503, daily quota; ADR-014). Read by `application/runtime/step/model_selection.py`.

## 1. File format

```json
{
  "schema_version": 1,
  "name": "claude_mixed",
  "_about": "free text for people; keys that start with _ are ignored",
  "default": ["claude-haiku-4-5"],
  "project_manager": ["claude-sonnet-5-5"],
  "draft_writer": ["claude-sonnet-5-5", "claude-haiku-4-5"]
}
```

| Key | Required | Values | Meaning |
|---|---|---|---|
| `schema_version` | yes | `1` | Whole number; no other version loads. |
| `name` | recommended | same text as the file name without `.json` | If present and different from the file name, the file is refused. |
| `default` | one of `default` or a step is required | list of model ids | Used by every step that has no entry of its own. |
| `<step name>` | no | list of model ids | A model list for that one step (the names in section 2). |
| `_anything` | no | any | A comment. **Use `_about`, not `about`:** a key `about` is read as a step name and the set is refused (`unknown step 'about'`). |

Rules checked by `scripts/check_agent.py` (and at start, where a set with a problem disables the profiles that use it):

- Each list must be **non-empty** and every id must be in the **model catalog** (`domain/value_objects/llm_request/model_catalog.py`, section 3). A typo is an error, never ignored.
- A step key that is not in the list of section 2 is an error. A set needs `default` or at least one step.
- The **whole list is replaced**, never merged: a step entry does not inherit the `default` fallbacks. Repeat them if you want them.
- A list can hold models of **different providers** (for example Claude first, Gemini as fallback); each needs its own API key in the environment, and a missing key only shows when that model is called.
- A file or folder whose name starts with `_` is not loaded (use `_old_balanced.json` to retire a set without deleting it).
- A set is not used until a profile names it. `scripts/check_agent.py` still checks every set, used or not.

## 2. Step names a set may use

| Step | Group | Note |
|---|---|---|
| `triage_specialist` | identification | classifies the message |
| `project_manager` | special | the planner |
| `safety_quality_gatekeeper` | special | safety gate |
| `cognitive_worker` | special | one call per action that needs no tool |
| `mcp_operator` | special | one call per tool action |
| `data_engineer` | special | cleans a tool result |
| `draft_writer` | common | first text of the reply |
| `editor_in_chief` | common | final text |
| `answer_checker` | runtime | decides if the next message answers a question |
| `user_clarification` | runtime | turns missing data into a question |
| `motion_planner` | movement | arm movements |
| `emotion_reader` | expression | emotion of an exchange |

`action_executor`, `motion_validator` and `gesture_builder` are plain code: they have no model and are refused as keys. A new LLM step declared in `step_defs/` becomes a valid key automatically (see [step_defs/README.md](../step_defs/README.md)). The cost, budget and rating tables in `docs/models/` cover only the first ten (the text flows).

## 3. Model ids you can write

Exact ids of the catalog (2026-10-27; some are deprecated or have a shutdown date, see the comments in the catalog file and the prices in `config/{gemini_models,other_models}.json`):

- **Google** (`GOOGLE_API_KEY`): `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3-flash-preview`.
- **Anthropic** (`ANTHROPIC_API_KEY`): `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-sonnet-5`, `claude-haiku-4-5`.
- **OpenAI**: `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.2`, `gpt-5.1`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-4o`, `gpt-4o-mini`, `o3-mini`.
- **Groq**: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`.
- **Cohere**: `command-a-plus-05-2026`, `command-a-03-2025`, `command-a-reasoning-08-2025`, `command-a-vision-07-2025`, `command-r-08-2024`, `command-r-plus-08-2024`.
- **Ollama** (`OLLAMA_URL`): `llama4`, `llama3.3`, `phi4`, `deepseek-v3`, `mistral-nemo`.
- **Mistral**: the catalog has no usable id yet.

A new model is a **code change** (the catalog and its price in `config/`), not a file here.

## 4. Limits to know before you write a set

- **Claude**: runs through Anthropic's OpenAI-compatible endpoint with a strict, sanitized schema. An answer schema may nest at most 3 levels; a step whose schema breaks that is refused when a profile puts a Claude model on it (`scripts/check_agent.py` says which). The endpoint hides Claude's thinking, so the cost tables understate the cost of the larger Claude steps. The shipped Claude sets are one-item lists on purpose.
- **Google free tier**: no published limits and a daily cap per model (about 20 requests on some). Use fallbacks for steps that run often.
- **Tools**: a model that cannot call tools well should not be on `mcp_operator`/`project_manager` of a profile with tools; nothing here checks that, only a real run does (`scripts/run_profile.py`, it costs money).
- A set says nothing about **tools, prompts or flows**: only models.
- A model set is a *name*; the real choice happens per profile, with a precedence order (section 5).

## 5. How a profile uses a set (precedence)

The most specific level of the profile wins; the list found is used whole:

1. `flows.<flow>.steps.<step>.models`
2. `overrides.<step>.models`
3. `flows.<flow>.models`
4. `models` (a set name or a list of ids)
5. the step's own `default_models` in `step_defs/` (a Google model) when nothing above says anything

A level is a **set name** or a **list of ids**. Within a set, the step's own entry wins over `default`. No environment variable chooses a model any more. `python scripts/check_agent.py --explain <profile>` prints, per step, the model that answers and which level chose it.

## 6. The sets here

| Set | Idea | Used by |
|---|---|---|
| `proven` | everything on `gemini-3.1-flash-lite` with two Google fallbacks | `default`, `identification`, `movement`, `gesture` |
| `claude_haiku` | Haiku 4.5 everywhere, Sonnet 5.5 for the planner | `chat` |
| `claude_fast` | Haiku 4.5 on the tool selector and the answer writer (ADR-019) | `dynamics_fast` |
| `claude_mixed` | Haiku 4.5, Sonnet 5.5 for planner, writer and editor | `special`, `dynamics` |
| `claude_sonnet` | Sonnet 5 everywhere (legacy id) | nobody (untested) |
| `google_free` | Google free-tier models with two fallbacks per step | nobody |
| `balanced`, `budget`, `budget50`, `budget50_groq`, `quality` | cost/quality variants (the `budget50*` ones fit 50 EUR for 1,000 messages at paid prices) | nobody (untested) |

The `_about` of each file holds the details and the dated notes. Regenerate the cost tables after changing a set: `python scripts/model_tables.py --write` (`docs/models/` is generated; do not edit it by hand), and update `docs/configuration/environment-variables.md` section 3.
