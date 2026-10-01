> **HISTORICAL (banner added 2026-10-01).** Questions asked on 2026-09-21 before the orchestrator fixes. The answers and what was done are in `orchestrator_decisions.md`; the current design is in `README.md`.

# Orchestrator questionnaire

Questions I need answered before fixing the problems of `docs/orchestrator_report.md`. Each one has the finding it belongs to, why I cannot decide it alone, the options, and what I would pick. Answer with the number and a letter (for example "1A, 2B") or write your own answer. If you have no preference, "your pick" is fine and I will use the recommended option.

Questions marked **[blocks]** stop me from starting that fix. The others have a safe default.

## Product decisions (they shape everything else)

### Q1. What should the agent return to Brain? **[blocks]** (open decision of the report)
Today it returns only the reply text.
- **A. Text only** (recommended for now). Brain speaks it.
- **B. Text plus a structured decision**, for example `{"reply": "...", "brain_actions": [{"type": "move_arm", ...}]}`. Then I need to know which actions Brain can perform and the fields each one takes.
- **C. Text plus the intent and status only** (`intent`, `next_step.status`), so Brain can react to "waiting for confirmation" or "done".

>Combination of B and C

### Q2. What language and style should the spoken reply have? (finding E)
Nothing sets language, tone, length or format, so replies can be long, in the wrong language, or full of Markdown.
- Which language(s)? Always Spanish, always English, or the language of the user's message?
- Maximum length? (for example "at most 2 sentences unless asked for more")
- Plain spoken text only (no lists, no Markdown, no emojis)?
- **Where should this be decided?** A. Fixed defaults in code (recommended). B. The triage phase decides per request. C. Both: defaults, and triage can override.

>For now the language is english, but in the future it need to aswear the last phase (the one the user recieves) in the original language. The length tone for now i dont care, it can get as long as the AI needs

### Q3. Should small talk go through the full chain? (findings L, O)
"Hello" today costs 5 to 6 sequential calls and forces at least one planned action.
- **A. Keep the chain for everything** (no behavior change, slow).
- **B. Fast path:** if triage says no actions are needed, skip phases 2 to 6 and go straight to a single answer call (recommended, changes behavior).
- **C. Fast path only for a short list of intents** (for example greetings, `clarification_request`).
- How long may a reply take for the robot? For example 3 s, 5 s, 10 s. This decides how far to go.

>Depending on the task_category.complexity if its low it can be passed, on the orquestrator it needs to decide when the action that needs tto be doone is low it can go on the phases ifnot make subactions until de complexity is low (max subactions 10, for now)

## Correctness of the flow

### Q4. Spelling of the two mismatched fields (findings A, B)
The schema says `requested_user_input` and `subactions`. The prompts, mapper and domain say `request_user_input` and `subtasks`.
- **A. Change the code to follow the schema** (`requested_user_input`, `subactions`). Smallest change, prompts need two word replacements. Recommended.
- **B. Change the schemas and prompts to follow the code.** More files to keep in sync.
- Are there other places outside `ai-agent` (Brain, contracts) that already use one of the spellings?

>A

### Q5. How deep should plans go? (finding B)
Once subactions work, each one costs LLM calls in phases 4 and 6.
- **A. Allow full recursion** as the prompt says.
- **B. Limit to one level** (recommended: predictable cost).
- **C. No subactions at all** (flat plans). Then I remove them from the prompt and schema.
- Is there a maximum number of actions per plan you accept (for example 6)?

>A, because if the action is complex it needs to make it easier to reduce LLMs allucinations and errors. Max of 10 subactions

### Q6. MCP server id and tool names in the plan (findings C, H)
`server_id` has an empty enum, and the planner does not know the tool names.
- **A. Fill `server_id` with the real server names for each request, and give the planner the tool names and descriptions** (recommended).
- **B. Let the planner only say "use MCP" and let phase 5 pick server and tool from the tools it is given.** Simpler, less predictable.
- Which MCP servers do you actually want the agent to use now? Only `aws_microservice`? Should `fetch` and `filesystem` be supported (they need Docker and stdio support), or removed from `mcps/`?
- Is `aws_microservice` reachable from where the agent runs, and what tools does it offer today? (I can list them if you start it.)

>for now the MCP binding are not prioritary. But in case you needed A

### Q7. Order and dependencies between actions (finding D)
Today all cognitive actions run first, then all MCP actions, so dependencies across types break.
- **A. Run actions in dependency order** whatever their type (recommended).
- **B. Keep the two blocks** but share the results between them. Still fails when a cognitive action needs an MCP result.
- If an action fails (or is blocked), what should the dependents do? A. Skip them and tell the user what failed. B. Run them anyway without that input. C. Stop the whole run.

>The thing is that each action can depend on anotherone so it needs to make a way to handle and process all the actions in order until all is processed, in case the action requires another or multiple actions, the new action call needs the output and information of the related action so it can be precise

### Q8. What should happen when a tool fails? (finding H)
- **A. Tell the user briefly what failed and continue with what worked** (recommended).
- **B. Retry once, then A.**
- **C. Stop and say the request could not be completed.**
- Should the reply mention technical details, or stay generic ("I could not reach the service")?

>B

## Asking the user and confirmations

### Q9. Should the triage phase be able to ask questions? (finding F)
- **A. Yes, pause right after triage when it says `awaiting_user_input`** (recommended: saves 2 calls).
- **B. No, leave the question to the planner.**

>A


### Q10. How should a confirmation work? (finding G)
Today "yes" starts a new run and the safety gate probably asks again.
- **A. Store the pending plan in the session; the next "yes" runs it directly, "no" cancels it** (recommended).
- **B. Keep re-planning, but tell the safety gate the user already confirmed** (put "user confirmed" in the history).
- **C. Skip confirmations entirely** (only if the agent never does anything irreversible).
- Which kinds of actions must always ask first? For example: sending messages, deleting or writing files, calling paid services, moving the arms.
- How should a confirmation question sound (one short yes/no question)? And what counts as "yes" in your language (any of "si", "vale", "ok", "adelante")?

>B, but take into accounf that each ask of the user make a response, that is completed step by step, it must resume where the step was waiting for the user, so all the previos context is not missing, and it doesnt restart all the process


### Q11. When the user gives missing information, should the old plan continue? (finding G)
- **A. Yes, resume the paused plan** with the new input (needs stored state, cheaper).
- **B. No, start again from the history** (current behavior, simpler).

>A

### Q12. What if the final editor says the answer is incomplete? (finding I)
- **A. Speak the reply anyway** (current).
- **B. Ask the user the missing question instead** (recommended).
- **C. Retry the draft once.**

>B, but also A (for context)


## Reliability, cost, and quality

### Q13. Which model should each phase use? (findings K, L)
Defaults are `gpt-4.1-mini` for triage and `gpt-4.1` for the rest, all at temperature 1.0.
- Is a cheaper or faster model acceptable for phases 1, 3 and 6 (classification and cleaning)?
- Should JSON phases use a lower temperature (for example 0.2)? I recommend yes for phases 1 to 3 and 6.
- Is GitHub Models the provider you want to keep, and what is your monthly budget or rate limit? (The free tier has low request limits, and 6+ calls per message can hit them.)

>for now i dont specify exactly what it needs, i will make a custom way to know what would be the best but for now leave it as it is.

### Q14. Data cleaning phase (finding L)
- **A. Run phase 6 only on MCP outputs** (recommended).
- **B. Keep running it on every output.**
- **C. Remove phase 6** and let the writer clean what it needs.

>A


### Q15. What should happen when the LLM returns invalid or empty JSON? (general)
Today the whole message fails.
- **A. Retry the same call once, then fail with a short spoken apology** (recommended).
- **B. Fail immediately** (current).
- What should the robot say when it fails? (one fixed sentence in your language)

>A

### Q16. Should unknown statuses do something? (finding M)
`retry`, `error`, `complete` and `retry_action_id` exist in the schema but nothing reacts.
- **A. Ignore them and remove them from the schema** (recommended: less to go wrong).
- **B. Implement them:** `retry` re-runs the action in `retry_action_id`, `error` ends the run with an apology.

>B. Retry 3 times, and if the third one also fails returns apology


### Q17. Enforce the action types? (finding N)
- **A. Reject unknown `action_type` values in the domain and treat `clarification` actions as "ask the user"** (recommended).
- **B. Leave as is.**

>B, but it must try 3 times before asking the user, because the user will not know exactly what to put so it only provides context

### Q18. Input format for the LLM (finding J)
Prompts get Python `repr` text instead of JSON.
- **A. Switch to JSON** (cleaner, fewer tokens, changes every input, re-records the golden test). Recommended, but last.
- **B. Leave as is.**

>A

## Practical questions

### Q19. May I make one real LLM call now? **[blocks the schema fixes]**
It is the only way to confirm whether GitHub Models accepts the schemas (finding C), returns bare JSON, and how long a call takes. It would cost a few calls of `gpt-4.1` and `gpt-4.1-mini`.
- **A. Yes, one message** (for example "what is 2+2") through the full chain, and I report time, tokens and any schema rejection.
- **B. Yes, but three messages:** small talk, a request that needs a question back, and one that needs the MCP server.
- **C. No, I will run it myself** (`tests/manual/full_flow_real_llm.py`) and paste the result.

>B

### Q20. Example conversations
Please give me 5 to 10 real things you expect the robot to be asked, with the answer you would like, including at least:
- a simple question,
- something that needs an MCP tool,
- something that needs a question back,
- something that needs confirmation,
- something the robot should refuse.

I will turn them into tests that fix the expected behavior with a scripted LLM, and into the manual script for the real one.


>Which day is today?. How many emails do I have?. My family has 4 people make a table of each name. (it must ask the names of each member of my family to generate the table). CAn you delete this file?. Can you jump? (the robbot doesnt have the ability)

### Q21. Priority
Which do you want first?
- **A. Make it work correctly for a simple case** (findings A, B, C, D, then Q19).
- **B. Make it fast enough for voice** (Q3, Q13, Q14).
- **C. Make it safe** (confirmations, tool failures: Q8, Q10, Q11).
- **D. Connect it to Brain** with the current text reply, then improve.

>A


## How the answers map to the fixes

| Finding | Questions |
|---|---|
| A, B (mapper) | Q4, Q5 |
| C (server id enum) | Q6, Q19 |
| D (dependencies) | Q7 |
| E (constraints) | Q2 |
| F (triage pause) | Q9 |
| G (confirmation loop) | Q10, Q11 |
| H (MCP errors, tool names) | Q6, Q8 |
| I (editor status) | Q12 |
| J (repr input) | Q18 |
| K, L (temperature, cost) | Q3, Q13, Q14 |
| M, N, O | Q16, Q17, Q3 |
| Open decision (reply type) | Q1 |
