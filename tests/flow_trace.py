"""
Debugging aid. It only COORDINATES the real code and writes what you want to a file:

- the steps are the real steps of `Pipeline` (real phases, real runner, real action executor, real mapper);
  the only thing that can be replaced is the LLM (`llm`: the scripted one of the tests, or the real adapter);
- after each LLM call and after its data was loaded into the object of the flow (`FlowState`),
  one markdown file is written: the request sent to the LLM at the top, the full object at the bottom.

Nothing here knows how a phase works. Objects are written generically (`to_plain`), and what changed is
found by comparing the object before and after.

For debugging each part:
- every raw answer is checked against the JSON schema that was sent with the request, and for text that
  looks wrong (`problems_of`); the problems are written in the files, next to the answer;
- the state each step received is saved (`save_step_inputs`), so ONE step can be run again alone, any number
  of times, with exactly the same input (`trace_step`), and the runs compared (`compare_runs`).
"""
import copy
import json
from contextlib import contextmanager
import os
import re
import sys
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.flow_state import FlowState
from application.orchestration.metrics import SessionMetrics
from application.orchestration.pipeline import Pipeline
from domain.entities.response import Response

# Every field of FlowState that holds the result of a phase (the message and the history are inputs).
STATE_FIELDS = [f.name for f in fields(FlowState) if f.name not in ("message", "history")]


# ===============================================
#  OBJECTS AS PLAIN DATA (generic)
# ===============================================

def to_plain(obj: Any) -> Any:
    """Any domain object as plain data. A value object that only wraps a `value` becomes that value."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]
    if is_dataclass(obj):
        names = [f.name for f in fields(obj)]
        if names == ["value"]:
            return to_plain(getattr(obj, "value"))
        return {name: to_plain(getattr(obj, name)) for name in names}
    return repr(obj)


def snapshot(state: FlowState) -> Dict[str, Any]:
    """The whole object of the flow as plain data."""
    data = {"message": state.message, "history_turns": len(state.history)}
    for name in STATE_FIELDS:
        value = to_plain(getattr(state, name))
        data[name] = None if value in ([], {}) else value        # an empty list is "nothing yet"
    return data


def response_plain(response: Response) -> Dict[str, Any]:
    """The fields the mapper filled in a Response (the ones that are not None), as plain data."""
    skip = {"tokens_usage", "raw"}
    return {f.name: to_plain(getattr(response, f.name)) for f in fields(response)
            if f.name not in skip and getattr(response, f.name) is not None}


def _strings(node: Any, path: str = ""):
    if isinstance(node, str):
        yield path or "(root)", node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


def problems_of(raw: Any, schema: Optional[dict], text: Optional[str] = None) -> List[str]:
    """
    What is wrong with an answer, without knowing the phase:
    - it does not follow the JSON schema that was sent (missing or extra keys, wrong type, value outside an enum);
    - it should have been a JSON object and it was not;
    - a text holds a literal backslash-n (a double-escaped line break), which would be spoken or shown as `\\n`.
    """
    problems: List[str] = []

    if schema is not None and not isinstance(raw, dict):
        problems.append(f"answer: the request asked for a JSON object and the LLM answered {text!r}"[:300])

    if schema is not None and isinstance(raw, dict):
        import jsonschema
        try:
            errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(raw), key=lambda e: list(e.absolute_path))
        except Exception as error:                                   # a schema the validator cannot read
            errors = []
            problems.append(f"schema: could not be checked ({type(error).__name__}: {str(error)[:120]})")
        for error in errors[:20]:
            where = "/".join(str(p) for p in error.absolute_path) or "(root)"
            problems.append(f"schema: {where}: {error.message[:220]}")

    for where, value in _strings(raw if raw is not None else text):
        if "\\n" in value:
            problems.append(f"text: {where} holds a literal backslash-n instead of a line break")

    return problems


def _mark(before: Any, after: Any) -> str:
    if before is None and after is None:
        return "."
    if before is None:
        return "SET"
    return "CHG" if before != after else "="


# ===============================================
#  WHAT IS RECORDED
# ===============================================

@dataclass
class CallTrace:
    """One LLM call: the request that was sent, the raw answer, and the Response object it became."""
    step: str
    format_name: str
    model: str
    temperature: Optional[float]
    max_tokens: Optional[int]
    tool_names: List[str]
    system_prompt: str
    user_message: str
    schema: Optional[dict]
    raw: Optional[dict]
    text: Optional[str]
    response: Dict[str, Any]                            # the filled fields of the Response, as plain data
    ignored: List[str] = field(default_factory=list)    # keys of the raw answer that no Response field has
    problems: List[str] = field(default_factory=list)   # what is wrong with the answer (see problems_of)
    error: Optional[str] = None                         # the call or the mapper raised: no Response was built
    prompt_tokens: Optional[int] = None                 # tokens sent (what the provider counted)
    completion_tokens: Optional[int] = None             # tokens answered (Gemini does NOT count its thinking here)
    total_tokens: Optional[int] = None                  # what the provider billed as used: sent + answered + thinking

    @property
    def thinking_tokens(self) -> Optional[int]:
        """Tokens the model thought before answering: total - sent - answered (Gemini counts them only in the total)."""
        if None in (self.prompt_tokens, self.completion_tokens, self.total_tokens):
            return None
        return max(0, self.total_tokens - self.prompt_tokens - self.completion_tokens)

    @property
    def filled(self) -> List[str]:
        return list(self.response)

    @property
    def system_prompt_chars(self) -> int:
        return len(self.system_prompt)


@dataclass
class Modification:
    """One change of the flow object: the call to the LLM, and the object before and after its data was loaded."""
    number: int
    step: str
    call: CallTrace
    before: Dict[str, Any]
    after: Dict[str, Any]

    @property
    def changes(self) -> Dict[str, tuple]:
        """field -> (SET or CHG, before, after) for the fields this call changed."""
        return {name: (_mark(self.before[name], self.after[name]), self.before[name], self.after[name])
                for name in STATE_FIELDS if self.before[name] != self.after[name]}


@dataclass
class StepTrace:
    index: int
    step: str
    calls: List[CallTrace] = field(default_factory=list)
    changes: Dict[str, tuple] = field(default_factory=dict)    # field -> (SET or CHG, before, after)
    state: Dict[str, Any] = field(default_factory=dict)        # the whole object after the step
    marks: Dict[str, str] = field(default_factory=dict)        # field -> SET | CHG | = | .
    input_state: Any = None                                    # a copy of the FlowState the step received

    @property
    def problems(self) -> List[str]:
        return [f"{c.format_name}: {p}" for c in self.calls for p in c.problems]

    @property
    def responses(self) -> List[CallTrace]:
        return self.calls

    @property
    def changed(self) -> Dict[str, tuple]:
        return {k: (v[1], v[2]) for k, v in self.changes.items()}


# What the real adapter got back from the LLM, kept even when the mapper then rejects it.
CAPTURED: Dict[str, Any] = {}


@contextmanager
def _capture_raw_text():
    """
    While active, the text the real adapter receives from `generate_text` is kept in CAPTURED["text"].
    Without it, an answer the mapper rejects would be lost. It changes nothing in the real code.
    """
    import infrastructure.outbound.llm.vercel as vercel
    original = vercel.generate_text

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        CAPTURED["text"] = getattr(result, "text", None)
        return result

    vercel.generate_text = wrapper
    try:
        yield
    finally:
        vercel.generate_text = original


class StopTrace(Exception):
    """Raised by an `on_step` callback to end the trace after the current step."""


class _Recorder:
    """
    Stands in for the LLM port: passes every call to the real LLM (or the scripted one) and keeps it.
    A call is closed when the next call starts or the step ends, because by then its data is loaded.
    """

    def __init__(self, inner):
        self.inner = inner
        self.calls: List[CallTrace] = []
        self.modifications: List[Modification] = []
        self.state: Optional[FlowState] = None
        self.step_name = ""
        self._pending: Optional[CallTrace] = None
        self._before: Optional[Dict[str, Any]] = None

    def bind(self, state: FlowState, step_name: str) -> None:
        self.state, self.step_name = state, step_name
        if self._before is None:
            self._before = snapshot(state)

    def close(self) -> None:
        if self._pending is None or self.state is None:
            return
        after = snapshot(self.state)
        self.modifications.append(Modification(len(self.modifications) + 1, self._pending.step,
                                               self._pending, self._before, after))
        self._before, self._pending = after, None

    def _call(self, payload, raw, text, plain, ignored, error=None, usage=None) -> CallTrace:
        schema = payload.response_format.schema if payload.response_format else None
        problems = problems_of(raw, schema, text)
        if error:
            problems.insert(0, f"call: no Response was built, {error}")
        return CallTrace(
            step=self.step_name,
            format_name=payload.response_format.name if payload.response_format else "text",
            model=payload.model.id,
            temperature=payload.temperature.value if payload.temperature else None,
            max_tokens=payload.max_tokens.value if payload.max_tokens else None,
            tool_names=[t.get("name", "?") if isinstance(t, dict) else getattr(t, "name", "?")
                        for t in (payload.tools or [])],
            system_prompt=payload.system_prompt.content if payload.system_prompt else "",
            user_message=payload.message.content,
            schema=schema, raw=raw, text=text, response=plain, ignored=ignored, problems=problems, error=error,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
        )

    def ask(self, payload):
        self.close()
        CAPTURED.clear()
        if hasattr(self.inner, "last_raw"):
            self.inner.last_raw = None
        try:
            response = self.inner.ask(payload)
        except Exception as error:
            # The answer was not usable (or the call failed). Keep what came back, so it can be read.
            text = CAPTURED.get("text")
            raw = getattr(self.inner, "last_raw", None)
            if raw is None and text:
                try:
                    raw = json.loads(text)
                except ValueError:
                    raw = None
            call = self._call(payload, raw, text if raw is None else None, {}, [], f"{type(error).__name__}: {str(error)[:300]}")
            self.calls.append(call)
            self._pending = call
            raise

        call = self._call(payload, response.raw, response.text, response_plain(response),
                          [k for k in (response.raw or {}) if k not in {f.name for f in fields(response)}],
                          usage=response.tokens_usage)
        self.calls.append(call)
        self._pending = call
        return response


def trace_flow(
    message: str,
    llm,
    mcp_list: Optional[list] = None,
    on_step: Optional[Callable[[StepTrace], None]] = None,
    modifications: Optional[List[Modification]] = None,
    failures: Optional[List[Exception]] = None,
) -> List[StepTrace]:
    """
    Runs the message through the real `Pipeline` and returns one StepTrace per step that ran.
    `on_step` is called right after each step (raise StopTrace to end there). A question written for the user
    is the last "step". If `modifications` is a list, it is filled with one Modification per LLM call.
    If the flow fails, the trace up to the failure is kept, and the exception goes to `failures` (if given).
    """
    recorder = _Recorder(llm)
    pipeline = Pipeline(recorder, mcp_list or [], SessionMetrics())
    traces: List[StepTrace] = []
    previous = {name: None for name in STATE_FIELDS}
    seen = {"calls": 0}

    def finish(step_name: str, state_data: Dict[str, Any], input_state: Any = None) -> StepTrace:
        marks = {name: _mark(previous[name], state_data[name]) for name in STATE_FIELDS}
        trace = StepTrace(
            index=len(traces) + 1, step=step_name, calls=recorder.calls[seen["calls"]:],
            changes={n: (marks[n], previous[n], state_data[n]) for n in STATE_FIELDS if marks[n] in ("SET", "CHG")},
            state=state_data, marks=marks, input_state=input_state)
        seen["calls"] = len(recorder.calls)
        previous.update({name: state_data[name] for name in STATE_FIELDS})
        traces.append(trace)
        return trace

    def traced(step):
        def run(state: FlowState) -> None:
            recorder.bind(state, step.name)
            input_state = copy.deepcopy(state)               # what this step received
            step.run(state)                                  # the real step
            recorder.close()
            recorder.step_name = "user_question"             # a call made after the steps is the question for the user
            trace = finish(step.name, snapshot(state), input_state)
            if on_step:
                on_step(trace)
        return run

    pipeline.steps = [replace(step, run=traced(step)) for step in pipeline.steps]

    try:
        with _capture_raw_text():
            pipeline.run(message)                            # the real orchestrator
    except StopTrace:
        pass
    except Exception as error:                               # the flow failed: keep the calls that were made
        if failures is not None:
            failures.append(error)
    else:
        if len(recorder.calls) > seen["calls"]:
            trace = finish("user_question", dict(previous, message=message, history_turns=0))
            if on_step:
                try:
                    on_step(trace)
                except StopTrace:
                    pass

    recorder.close()
    if modifications is not None:
        modifications.extend(recorder.modifications)
    return traces


# ===============================================
#  ONE MARKDOWN FILE PER MODIFICATION
# ===============================================

def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def format_modification_md(mod: Modification, title: str = "") -> str:
    """Top: the request sent to the LLM. Bottom: the full object of the flow after the data was loaded."""
    call = mod.call
    lines = [f"# {mod.number:02d}. {mod.step}: {call.format_name}"]
    if title:
        lines.append(f"\n_{title}_")

    lines += [
        "\n## 1. Request sent to the LLM",
        f"\n- model: `{call.model}`",
        f"- temperature: `{call.temperature}`, max tokens: `{call.max_tokens}`",
        f"- response format: `{call.format_name}`",
        f"- tools: {', '.join(f'`{n}`' for n in call.tool_names) or 'none'}",
        f"- tokens: {call.prompt_tokens} sent, {call.completion_tokens} answered, {call.thinking_tokens} thinking" if call.prompt_tokens is not None
        else "- tokens: not counted",
        f"\n### User message ({len(call.user_message)} chars)",
        "\n```text", call.user_message, "```",
        f"\n<details><summary>System message ({call.system_prompt_chars} chars)</summary>",
        "\n```text", call.system_prompt, "```", "\n</details>",
    ]
    if call.schema is not None:
        lines += ["\n<details><summary>Response format (JSON schema)</summary>",
                  "\n```json", _json(call.schema), "```", "\n</details>"]

    lines += ["\n## 2. Raw answer of the LLM"]
    lines += ["\n```json", _json(call.raw), "```"] if call.raw is not None else ["\n```text", str(call.text), "```"]

    lines += [f"\n## 3. Problems found in the answer ({len(call.problems)})"]
    lines += [f"\n- {p}" for p in call.problems] if call.problems else ["\nNone: the answer follows the schema."]

    lines += [f"\n## 4. Response object built by the mapper: `Response({', '.join(call.filled) or 'text only'})`"]
    if call.error:
        lines += [f"\n**NOT BUILT.** {call.error}", "\nNothing was loaded into the flow object by this call."]
    if call.response:
        lines += ["\n```json", _json(call.response), "```"]
    for key in call.ignored:
        lines.append(f"- **Not read by the mapper:** `{key}`")

    lines += ["\n## 5. What this call changed in the flow object"]
    if not mod.changes:
        lines.append("\nNothing.")
    for name, (mark, before, after) in mod.changes.items():
        if mark == "SET":
            lines += [f"\n**{name}**: SET", "```json", _json(after), "```"]
        else:
            lines += [f"\n**{name}**: CHANGED", "\nWas:", "```json", _json(before), "```",
                      "Now:", "```json", _json(after), "```"]

    lines += ["\n## 6. Full object of the flow after the data was loaded", "\n```json", _json(mod.after), "```", ""]
    return "\n".join(lines)


def write_markdown_files(mods: List[Modification], out_dir: str, title: str = "") -> List[str]:
    """Writes one file per modification plus `00_index.md`. Returns the paths of the per-call files."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    index = [f"# Flow trace{': ' + title if title else ''}", "", "| # | step | LLM call | changed | problems |", "|---|---|---|---|---|"]

    for mod in mods:
        phase = re.search(r"phase(\d+)", mod.call.format_name)
        name = f"{mod.number:02d}_{_slug(mod.step)}_{'phase' + phase.group(1) if phase else 'text'}.md"
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(format_modification_md(mod, title))
        paths.append(path)
        index.append(f"| {mod.number} | {mod.step} | [{mod.call.format_name}]({name}) | "
                     f"{', '.join(mod.changes) or 'nothing'} | {len(mod.call.problems) or ''} |")

    with open(os.path.join(out_dir, "00_index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(index) + "\n")

    return paths


# ===============================================
#  STEP REPORT AND FIELD x STEP TABLE
# ===============================================

def _human(value: Any) -> str:
    return "(empty)" if value is None else json.dumps(value, ensure_ascii=False, default=str)


def format_step(trace: StepTrace, total: Optional[int] = None) -> str:
    title = f" STEP {trace.index}{'/' + str(total) if total else ''}: {trace.step} "
    lines = [title.center(78, "=")]

    for number, call in enumerate(trace.calls, 1):
        lines.append(f"\n[{number}/{len(trace.calls)}] LLM call {call.format_name}  model={call.model}  "
                     f"system prompt={call.system_prompt_chars} chars  tools={len(call.tool_names)}")
        lines.append("  INPUT (user message):\n" + "\n".join("      " + l for l in call.user_message.splitlines()))
        lines.append("  RAW ANSWER:\n" + "\n".join("      " + l for l in (
            _json(call.raw) if call.raw is not None else str(call.text)).splitlines()))
        lines.append("  RESPONSE OBJECT: NOT BUILT" if call.error else
                     f"  RESPONSE OBJECT: Response({', '.join(call.filled) or 'text only'})")
        for key in call.ignored:
            lines.append(f"      ! not read by the mapper: {key}")
        for problem in call.problems:
            lines.append(f"      ! PROBLEM {problem}")

    lines.append("\n  HOW THE FLOW OBJECT WAS COMPLETED BY THIS STEP:")
    if not trace.changes:
        lines.append("      nothing was written")
    for name, (mark, before, after) in trace.changes.items():
        if mark == "SET":
            lines.append(f"      + {name} SET      {_human(after)}")
        else:
            lines.append(f"      ~ {name} CHANGED\n            was: {_human(before)}\n            now: {_human(after)}")

    lines.append("\n  FLOW OBJECT AFTER THIS STEP:")
    for name in STATE_FIELDS:
        lines.append(f"      {trace.marks[name]:<3} {name:<22} {_human(trace.state[name])}")
    return "\n".join(lines)


def format_matrix(traces: List[StepTrace]) -> str:
    """A field x step table: how the flow object gets completed."""
    width = max(len(n) for n in STATE_FIELDS) + 2
    lines = ["STATE COMPLETION  (SET first filled, CHG overwritten, = kept, . still empty)",
             " " * width + "".join(f"{i + 1:>5}" for i in range(len(traces))) + "    "
             + "  ".join(f"{i + 1}={t.step}" for i, t in enumerate(traces))]
    for name in STATE_FIELDS:
        lines.append(f"{name:<{width}}" + "".join(f"{t.marks[name]:>5}" for t in traces))
    return "\n".join(lines)


def format_problems(traces: List[StepTrace], mods: Optional[List[Modification]] = None,
                    failures: Optional[List[Exception]] = None) -> str:
    """The problems of every answer. With `mods` it includes the calls of a step that failed."""
    if mods is not None:
        found = [(m.step, f"{m.call.format_name}: {p}") for m in mods for p in m.call.problems]
    else:
        found = [(t.step, p) for t in traces for p in t.problems]
    lines = [f"PROBLEMS FOUND IN THE ANSWERS: {len(found)}"]
    lines += [f"  {step}: {problem}" for step, problem in found]
    lines += [f"THE FLOW FAILED: {type(f).__name__}: {f}" for f in failures or []]
    return "\n".join(lines)


def format_trace(traces: List[StepTrace], mods: Optional[List[Modification]] = None,
                 failures: Optional[List[Exception]] = None) -> str:
    return "\n\n".join([format_problems(traces, mods, failures)] + [format_step(t, len(traces)) for t in traces]
                        + [format_matrix(traces)])


def write_report(traces: List[StepTrace], path: str, title: str = "", mods: Optional[List[Modification]] = None,
                 failures: Optional[List[Exception]] = None) -> str:
    """Saves the step-by-step report and the field x step table to a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Step-by-step report{': ' + title if title else ''}\n\n```text\n{format_trace(traces, mods, failures)}\n```\n")
    return path


def trace_to_markdown(message: str, llm, out_dir: str, mcp_list: Optional[list] = None, title: str = "") -> List[str]:
    """
    Runs the message through the real steps and saves everything to files in `out_dir`, nothing is printed:
    one markdown file per LLM call, `00_index.md`, and `report.md`. Returns the paths of the per-call files.
    """
    mods: List[Modification] = []
    failures: List[Exception] = []
    traces = trace_flow(message, llm, mcp_list, modifications=mods, failures=failures)
    paths = write_markdown_files(mods, out_dir, title or message)
    write_report(traces, os.path.join(out_dir, "report.md"), title or message, mods, failures)
    save_step_inputs(traces, out_dir)
    return paths


# ===============================================
#  DEBUGGING ONE PART ON ITS OWN
# ===============================================

def step_names(mcp_list: Optional[list] = None) -> List[str]:
    """The names of the steps of the real pipeline."""
    return [step.name for step in Pipeline(_Recorder(None), mcp_list or [], SessionMetrics()).steps]


def save_step_inputs(traces: List[StepTrace], out_dir: str) -> List[str]:
    """
    Saves the state each step received (`states/NN_<step>.pkl`), so that step can be run again alone
    with `trace_step`. These are Python pickles made by this tool: load only files you saved yourself.
    """
    import pickle
    folder = os.path.join(out_dir, "states")
    os.makedirs(folder, exist_ok=True)
    paths = []
    for trace in traces:
        if trace.input_state is None:
            continue
        path = os.path.join(folder, f"{trace.index:02d}_{_slug(trace.step)}.pkl")
        with open(path, "wb") as f:
            pickle.dump(trace.input_state, f)
        paths.append(path)
    return paths


def load_state(path: str) -> FlowState:
    import pickle
    with open(path, "rb") as f:
        return pickle.load(f)


def trace_step(step_name: str, state: FlowState, llm, mcp_list: Optional[list] = None):
    """
    Runs ONE real step of the pipeline (with its retries) on a copy of `state`.
    Returns (modifications, state after the step, whether the step leaves the flow waiting for the user).
    """
    recorder = _Recorder(llm)
    pipeline = Pipeline(recorder, mcp_list or [], SessionMetrics())
    step = next((s for s in pipeline.steps if s.name == step_name), None)
    if step is None:
        raise KeyError(f"unknown step {step_name!r}; the steps are: {', '.join(s.name for s in pipeline.steps)}")

    state = copy.deepcopy(state)
    recorder.bind(state, step.name)
    try:
        with _capture_raw_text():
            pipeline._run_step(step, state)             # the real step, as the orchestrator runs it
    except Exception:                                   # the failed calls are in the modifications
        recorder.close()
        return recorder.modifications, state, False
    recorder.close()
    waiting = bool(step.pause_if and step.pause_if(state))
    return recorder.modifications, state, waiting


def compare_runs(runs: List[List[Modification]], title: str = "") -> str:
    """
    Markdown that compares several runs of the same step on the same input: problems per run, and for each
    key of the raw answer whether the runs agree. It shows how much the LLM changes its answer.
    """
    lines = [f"# Runs of the same step compared{': ' + title if title else ''}", "",
             f"{len(runs)} runs, same input.", ""]
    calls = max((len(r) for r in runs), default=0)

    for position in range(calls):
        mods = [r[position] for r in runs if len(r) > position]
        lines += [f"## LLM call {position + 1}: {mods[0].call.format_name}", "",
                  "| run | problems | not read | changed in the flow object |", "|---|---|---|---|"]
        for number, mod in enumerate(mods, 1):
            lines.append(f"| {number} | {len(mod.call.problems)} | {', '.join(mod.call.ignored) or ''} | "
                         f"{', '.join(mod.changes) or 'nothing'} |")

        keys = sorted({k for m in mods for k in (m.call.raw or {})})
        lines += ["", "| key of the answer | runs agree |", "|---|---|"]
        for key in keys:
            values = [_json((m.call.raw or {}).get(key)) for m in mods]
            lines.append(f"| `{key}` | {'yes' if len(set(values)) == 1 else '**NO**'} |")

        for key in keys:
            values = [_json((m.call.raw or {}).get(key)) for m in mods]
            if len(set(values)) > 1:
                lines += ["", f"### `{key}` differs", ""]
                for number, value in enumerate(values, 1):
                    lines += [f"Run {number}:", "```json", value, "```"]

        problems = sorted({p for m in mods for p in m.call.problems})
        if problems:
            lines += ["", "### Problems seen", ""] + [f"- {p}" for p in problems]
        lines.append("")

    return "\n".join(lines)


def write_compare(runs: List[List[Modification]], path: str, title: str = "") -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(compare_runs(runs, title))
    return path


# ===============================================
#  STOPPING IN A DEBUGGER
# ===============================================

STOP_POINTS = ("start", "response", "loaded")
# start:    a step is about to run. `state` is what it received.
# response: an LLM answer just became a `Response`, and is NOT in the state yet. `payload` is the request, `response` the object.
# loaded:   the answer was loaded into the state (or, for the action executor, an action just got its output or error).


def _pause(kind, step=None, state=None, payload=None, response=None, action=None, phase_id=None):
    """
    The debugger stops here (the default `stop` of `run_with_stops`). Look at the variables of this frame:
        step      name of the step         state     the FlowState (the object that is completed)
        payload   the request sent         response  the Response built from the answer
        action    the action just settled  phase_id  the phase of the call
    Useful: `pp snapshot(state)`, `pp response_plain(response)`, `pp response.raw`, `pp payload.message.content`.
    `c` continues to the next stop, `q` quits.
    """
    label = {"start": "A STEP IS ABOUT TO RUN", "response": "AN ANSWER BECAME A Response (not in the state yet)",
             "loaded": "THE DATA WAS LOADED INTO THE STATE"}[kind]
    where = f" {step}" if step else ""
    print(f"\n>>> {label}:{where}" + (f" (phase {phase_id})" if phase_id else "")
          + (f" action {to_plain(action.id)}" if action is not None else ""))
    breakpoint()


def run_with_stops(
    message: str,
    llm,
    mcp_list: Optional[list] = None,
    at=("start", "loaded"),
    steps: Optional[List[str]] = None,
    stop: Optional[Callable[..., None]] = None,
):
    """
    Runs the message through the real `Pipeline` and calls `stop(kind, ...)` at the chosen points (`at`: any of
    STOP_POINTS), only for the steps in `steps` (default: all). `stop` defaults to a debugger (`breakpoint()`).
    Nothing of the real code is changed: the stops are placed around it while this function runs.
    Returns the FlowResult of the pipeline.
    """
    from unittest.mock import patch
    from application.orchestration.action_executor import ActionExecutor
    from application.orchestration.phase_runner import PhaseRunner

    stop = stop or _pause
    unknown = set(at) - set(STOP_POINTS)
    if unknown:
        raise ValueError(f"unknown stop points {sorted(unknown)}; use {STOP_POINTS}")

    pipeline = Pipeline(llm, mcp_list or [], SessionMetrics())
    current = {"step": None, "state": None}

    def selected() -> bool:
        return steps is None or current["step"] in steps

    def wrapped(step):
        def run(state: FlowState) -> None:
            current["step"], current["state"] = step.name, state
            if "start" in at and selected():
                stop("start", step=step.name, state=state)
            step.run(state)
            if "loaded" in at and selected():
                stop("loaded", step=step.name, state=state)
        return run

    pipeline.steps = [replace(step, run=wrapped(step)) for step in pipeline.steps]

    original_send = PhaseRunner.send
    original_succeed, original_fail = ActionExecutor._succeed, ActionExecutor._fail

    def send(self, payload, phase_id, model, action_id=None):
        response = original_send(self, payload, phase_id, model, action_id)
        if "response" in at and selected():
            stop("response", step=current["step"], state=current["state"], payload=payload, response=response,
                 phase_id=phase_id)
        return response

    def settled(original):
        def call(action, value, registry):
            original(action, value, registry)
            if "loaded" in at and selected():
                stop("loaded", step=current["step"], state=current["state"], action=action)
        return staticmethod(call)

    with patch.object(PhaseRunner, "send", send), \
            patch.object(ActionExecutor, "_succeed", settled(original_succeed)), \
            patch.object(ActionExecutor, "_fail", settled(original_fail)):
        return pipeline.run(message)
