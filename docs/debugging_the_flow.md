# Debugging the flow, part by part

Tool: `tests/manual/debug_flow.py` (with `tests/flow_trace.py`). It runs the **real steps** of the pipeline and only
coordinates them and writes files. Only the LLM can be replaced: the scripted one of the tests (free, offline), or the
real one with `--real` (it costs money; models come from `.env` and `AI_AGENT_MODEL_PHASE_<n>`).

## 1. Follow a whole message

```powershell
& windows\Scripts\python.exe tests\manual\debug_flow.py --real --name=table --message="Make a table of Ana and Luis"
```

Saves in `tests/output/debug/table/` (git-ignored):

| File | What it holds |
|---|---|
| `NN_<step>_phaseN.md` | One per LLM call. **1** the request sent (model, user message, system message, JSON schema). **2** the raw answer. **3** the problems found in it. **4** the `Response` object the mapper built. **5** what the call changed in the flow object. **6** the full flow object after the data was loaded. |
| `00_index.md` | The calls in order, with what each changed and how many problems it had. |
| `report.md` | The whole step-by-step report, the list of problems, and the field x step table. |
| `states/NN_<step>.pkl` | The state each step **received**. Used to run that step alone (below). |

Problems are found without knowing the phase: the answer does not follow the JSON schema that was sent (missing or
extra key, wrong type, value outside the allowed ones), the answer is not a JSON object, a text holds a literal `\n`
(a double-escaped line break), or the call or the mapper raised (then the raw answer is still kept, and the retries
show as separate calls).

## 2. Run one step alone, many times, with the same input

```powershell
& windows\Scripts\python.exe tests\manual\debug_flow.py --real --name=table --only=draft_writer `
    --state=tests\output\debug\table\states\05_draft_writer.pkl --repeat=5
```

Saves `only_draft_writer/run_1 ... run_5` (same files as above) and `compare.md`: for each key of the answer, do the
runs agree? If not, every version is shown side by side. Use `--steps` to list the step names. Only load `.pkl` files
you saved yourself.

## 3. Other options

`--print` prints the report on the console, `--print --interactive` waits after each step, `--scenario=NAME` scripts
the LLM with a scenario of the tests (`--list`), `--out=PATH` changes the folder.

## The same, inside the tests

`tests/test_flow_objects.py` uses the same tool with the scripted LLM. It fixes which step writes which field, checks
the problem detection, running one step alone, and comparing runs. When it runs it saves the files of every scenario in
`tests/output/flow_trace/<scenario>/` (or in `FLOW_TRACE_DIR`) and prints nothing.

## Stop in a debugger

```powershell
& windows\Scripts\python.exe tests\manual\debug_break.py                      # every stop
& windows\Scripts\python.exe tests\manual\debug_break.py --at=response --step=project_manager
& windows\Scripts\python.exe tests\manual\debug_break.py --real --message="Hello" --at=start,response,loaded
```

It runs the real pipeline and calls `breakpoint()` (pdb, or your IDE if you run it under the debugger) at these places.
Nothing of the real code is changed. `PYTHONBREAKPOINT=0` runs it without stopping.

| Stop | When | What to look at |
|---|---|---|
| `start` | a step is about to run | `state`: what the step received |
| `response` | an LLM answer just became a `Response`, **not in the state yet** | `payload` (the request), `response`, `response.raw` (the JSON the LLM answered) |
| `loaded` | the answer was loaded into the state; for the action executor, after each action got its output or error | `state` (the completed object), `action` |

In pdb: `pp snapshot(state)` (the whole flow object), `pp response_plain(response)`, `pp payload.message.content`,
`c` continue, `q` quit.

### Breakpoints in the real code (in an IDE)

If you prefer to put the breakpoints yourself, these are the places (line numbers of today, the names are stable):

| Where | File and function | Line |
|---|---|---|
| Start of every step | `application/orchestration/pipeline.py`, `Pipeline._run_step`, the `step.run(state)` line | 147 |
| The answer just became a `Response` (all phases) | `application/orchestration/phase_runner.py`, `PhaseRunner.send`, after `self.outbound_port.ask(payload)` | 120 to 130 |
| Where the `Response` object is built from the JSON | `infrastructure/outbound/llm/response_mapper.py`, `build_response`, the `return Response(` | 42 |
| Response loaded into the state, phases 1, 2, 3, 7, 8 | `application/orchestration/pipeline.py`, `build_steps`, `llm_phase`: `spec.apply(state, runner.run_phase(spec, state))` | 45 |
| The same, by phase (the fields that are copied) | `phases/triage.py` (`FlowState.load_from`, `flow_state.py:76`), `phases/project_manager.py:_apply` (49), `phases/safety_gate.py:_apply` (18), `phases/draft_writer.py:_apply` (16), `phases/editor_in_chief.py:_apply` (19) | |
| An action got its result | `application/orchestration/action_executor.py`: `_succeed` (195), `_fail` (200), `_set_output` (205) | |
| A run resumes after a question | `application/orchestration/pipeline.py`, `Pipeline._resume` | |

Best two for "where the full response is allocated": `PhaseRunner.send` (the `Response` exists, the state does not have
it yet) and `llm_phase` in `build_steps` / the `_apply` of each phase (the state is completed). The `debug_break.py`
stops `response` and `loaded` are exactly those two places.
