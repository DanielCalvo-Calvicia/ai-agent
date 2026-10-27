# Debugging the flow, part by part

Tools: `tests/manual/debug_flow.py` and `tests/manual/debug_break.py`, both built on `tests/flow_trace.py`. They run the
**real steps** of the pipeline and only coordinate them and write files; the only thing that can be replaced is the LLM:
the scripted one of the tests (free, offline) or the real one with `--real` (it costs money; models come from `.env`,
`config/step_models.json` and `AI_AGENT_MODEL_PHASE_<n>`).

## What they run (read this first)

The tools run the **text chain as one flow**: `FULL_FLOW` in `tests/flow_trace.py` is the identification flow's step followed
by the special flow's steps (triage, project manager, safety gate, action executor, draft writer, editor). That is the
chain a task goes through, and it lets you trace and re-run each step on its own.

They do **not** go through the router, so they do not show the routing to the conversation or movement flow, and they never
run the movement flow's steps. For those:

- routing, flows and pausing: `tests/test_router.py`, `tests/test_flows.py`, `tests/test_motion_flow.py`, `tests/test_resume.py`;
- a real process over HTTP with a scripted LLM: `contracts/tests/e2e/test_flow_separation.py` and
  `test_brain_ai_agent_flows.py` (workspace root);
- the router with a real LLM: `tests/manual/chat_session.py` or `full_flow_real_llm.py` (they send messages through the whole
  agent; they cost money).

The step names to use with `--only` and `--step`: `triage_specialist`, `project_manager`, `safety_quality_gatekeeper`,
`action_executor`, `draft_writer`, `editor_in_chief` (list them with `debug_flow.py --steps`).

## 1. Follow a whole message

```powershell
& windows\Scripts\python.exe tests\manual\debug_flow.py --real --name=table --message="Make a table of Ana and Luis"
```

Saves in `tests/output/debug/table/` (git-ignored):

| File | What it holds |
|---|---|
| `NN_<step>_phaseN.md` | One per LLM call: **1** the request sent (model, user message, system message, JSON schema); **2** the raw answer; **3** the problems found in it; **4** the `Response` the mapper built; **5** what the call changed in the flow object; **6** the full flow object after the data was loaded |
| `00_index.md` | the calls in order, with what each changed and how many problems it had |
| `report.md` | the whole step-by-step report, the list of problems and the field x step table |
| `states/NN_<step>.pkl` | the state each step **received**; used to run that step alone (section 2) |

Problems are found without knowing the phase: the answer does not follow the JSON schema that was sent (missing or extra key,
wrong type, a value outside the allowed ones), the answer is not a JSON object, a text holds a literal `\n` (a double-escaped
line break), or the call or the mapper raised (the raw answer is still kept, and retries show as separate calls).

## 2. Run one step alone, many times, with the same input

```powershell
& windows\Scripts\python.exe tests\manual\debug_flow.py --real --name=table --only=draft_writer `
    --state=tests\output\debug\table\states\05_draft_writer.pkl --repeat=5
```

Saves `only_draft_writer/run_1 ... run_5` (same files as above) and `compare.md`: for each key of the answer, do the runs agree?
If not, every version is shown side by side. Only load `.pkl` files you saved yourself.

## 3. Other options of `debug_flow.py`

`--print` prints the report on the console, `--print --interactive` waits after each step, `--scenario=NAME` scripts the LLM
with a scenario of the tests (`--list` shows them; the scenarios of the communication and movement flows are meant for the router,
not for this tool), `--out=PATH` changes the folder.

## 4. The same, inside the tests

`tests/test_flow_objects.py` uses the same tool with the scripted LLM. It fixes which step writes which field, checks the
problem detection, running one step alone and comparing runs. When it runs it saves the files of every scenario in
`tests/output/flow_trace/<scenario>/` (or in `FLOW_TRACE_DIR`) and prints nothing.

## 5. Stop in a debugger

```powershell
& windows\Scripts\python.exe tests\manual\debug_break.py                      # every stop
& windows\Scripts\python.exe tests\manual\debug_break.py --at=response --step=project_manager
& windows\Scripts\python.exe tests\manual\debug_break.py --real --message="Hello" --at=start,response,loaded
```

It runs the real pipeline and calls `breakpoint()` (pdb, or your IDE under the debugger) at these places. Nothing of the real
code is changed. `PYTHONBREAKPOINT=0` runs it without stopping.

| Stop | When | What to look at |
|---|---|---|
| `start` | a step is about to run | `state`: what the step received |
| `response` | an LLM answer just became a `Response`, **not in the state yet** | `payload` (the request), `response`, `response.raw` (the JSON the LLM answered) |
| `loaded` | the answer was loaded into the state (for the action executor, after each action got its output or error) | `state` (the completed object), `action` |

In pdb: `pp snapshot(state)` (the whole flow object), `pp response_plain(response)`, `pp payload.message.content`, `c` continue, `q` quit.

### Breakpoints in the real code (in an IDE)

Search for the names, not for line numbers (they move):

| Where | File and function |
|---|---|
| a step is about to run | `application/orchestration/engine/pipeline.py`, `Pipeline._run_step` (the `step.run(state)` line) |
| the router moves a message to a flow | `application/orchestration/flows/router.py`, `AgentRouter._answer` |
| the answer just became a `Response` (every phase) | `application/orchestration/engine/phase_runner.py`, `PhaseRunner.send`, right after `self.outbound_port.ask(payload)` |
| the `Response` is built from the JSON | `infrastructure/outbound/llm/response_mapper.py`, `build_response` |
| the response is loaded into the state | the `apply` of the phase (`_apply` in its file; triage uses `FlowState.load_from`), called from the flow's `llm_phase` |
| an action got its result | `application/orchestration/flows/action_executor.py`: `_succeed`, `_fail`, `_set_output` |
| a run resumes after a question | `application/orchestration/engine/pipeline.py`, `Pipeline._resume` |

The two best places for "where the full response is allocated" are `PhaseRunner.send` (the `Response` exists, the state does
not have it yet) and the `apply` of each phase (the state is completed): the `response` and `loaded` stops of `debug_break.py`.
