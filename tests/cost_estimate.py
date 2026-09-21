"""
Estimates what one message costs, per step, for a plan of a given size (default: 5 actions with 5 subactions
each = 30 actions).

The token model comes from real runs of this agent (tokens sent, answered and thinking per call, see the
`- tokens:` line of the files that `tests/manual/debug_flow.py --real` saves), scaled to the size of the plan.
It is an ESTIMATE: prices come from config/gemini_models.json and config/other_models.json, and the thinking
tokens are scaled from what gemini-3.8-flash and gemini-2.5-flash were measured to use.
`python tests/manual/estimate_cost.py` prints the table and `--write` saves docs/cost_of_a_full_plan.md.
"""
from dataclasses import dataclass
from typing import Any, Dict, List

from model_table import best_options, load_models

# ---- measured (real runs of this agent) ----------------------------------------------------------------------------
PROMPT = {                      # tokens sent by a call that has (almost) nothing to read: system prompt + schema + message
    "triage_specialist": 1260, "project_manager": 1600, "safety_quality_gatekeeper": 1130,
    "cognitive_worker": 1070, "mcp_operator": 1300, "data_engineer": 1000, "draft_writer": 1150,
    "editor_in_chief": 1090, "answer_checker": 1200, "user_clarification": 100,
}
ACTION_REPR = 68                # tokens that one action adds when the plan is written into a prompt (gate, draft)
PLANNER_TOKENS_PER_ACTION = 110  # tokens the planner writes for one action (id, description, type, dependencies, ...)
TRIAGE_OUTPUT, GATE_OUTPUT, PLANNER_BASE_OUTPUT = 150, 55, 120

# Thinking tokens per call of a model that thinks like gemini-3.8-flash. Measured with that model on a small plan
# (triage 489, planner 985, gate 231, worker 724, draft 344, editor 115). Gemini bills them as output but does not
# count them in `completion_tokens` (they are in `total_tokens`). Estimates: the planner thinks about twice as much
# for a plan of 30 actions; the tool steps and the checker are set like their nearest measured step.
THINKING = {"triage_specialist": 489, "project_manager": 1970, "safety_quality_gatekeeper": 231,
            "cognitive_worker": 724, "mcp_operator": 724, "data_engineer": 231, "draft_writer": 344,
            "editor_in_chief": 115, "answer_checker": 231, "user_clarification": 0}
# How much a model thinks compared with gemini-3.8-flash (1.0). Measured over a whole message: gemini-2.5-flash 0.69,
# gemini-3.1-flash-lite 0, gemini-2.5-flash-lite 0. The others are guesses from Google's descriptions.
THINKING_FACTOR = {"gemini-2.5-flash-lite": 0.0, "gemini-3.1-flash-lite": 0.0, "gemini-3.5-flash-lite": 0.1,
                   "gemini-2.5-flash": 0.7, "gemini-3.6-flash": 1.0, "gemini-3.7-flash": 1.0, "gemini-3.8-flash": 1.0,
                   "gemini-3.5-flash": 1.0, "gemini-2.5-pro": 1.5, "gemini-3.1-pro-preview": 1.5}

# ---- assumptions (not measured) ----------------------------------------------------------------------------------
ANSWER_TOKENS = 300             # what the worker writes for one action; a parent action writes 400
PARENT_ANSWER_TOKENS = 400
FINAL_ANSWER_TOKENS = 800       # the reply for the user (draft and editor)
TOOL_RESULT_TOKENS = 400


@dataclass
class StepUsage:
    step: str
    calls: int
    input_tokens: int          # in total, all the calls of the step
    output_tokens: int         # visible output, in total


def usage(actions: int = 5, subactions: int = 5, tool_actions: int = 5) -> List[StepUsage]:
    """The calls and tokens of every step for a plan of `actions` actions with `subactions` subactions each."""
    parents = actions
    nodes = actions * (1 + subactions)
    tool_actions = min(tool_actions, nodes - parents)              # tools run in leaf actions
    leaves = nodes - parents
    work_leaves, work_parents = leaves - tool_actions, parents

    # a leaf reads one dependency output, a parent reads the outputs of all its subactions
    worker_in = (work_leaves * (PROMPT["cognitive_worker"] + ANSWER_TOKENS)
                 + work_parents * (PROMPT["cognitive_worker"] + subactions * ANSWER_TOKENS))
    worker_out = work_leaves * ANSWER_TOKENS + work_parents * PARENT_ANSWER_TOKENS

    draft_in = PROMPT["draft_writer"] + ACTION_REPR * nodes + nodes * ANSWER_TOKENS

    return [
        StepUsage("triage_specialist", 1, PROMPT["triage_specialist"], TRIAGE_OUTPUT),
        StepUsage("project_manager", 1, PROMPT["project_manager"], PLANNER_BASE_OUTPUT + PLANNER_TOKENS_PER_ACTION * nodes),
        StepUsage("safety_quality_gatekeeper", 1, PROMPT["safety_quality_gatekeeper"] + ACTION_REPR * nodes, GATE_OUTPUT),
        StepUsage("cognitive_worker", work_leaves + work_parents, worker_in, worker_out),
        StepUsage("mcp_operator", tool_actions, tool_actions * (PROMPT["mcp_operator"] + ANSWER_TOKENS + 300),
                  tool_actions * 200),
        StepUsage("data_engineer", tool_actions, tool_actions * (PROMPT["data_engineer"] + TOOL_RESULT_TOKENS),
                  tool_actions * TOOL_RESULT_TOKENS),
        StepUsage("draft_writer", 1, draft_in, FINAL_ANSWER_TOKENS),
        StepUsage("editor_in_chief", 1, PROMPT["editor_in_chief"] + FINAL_ANSWER_TOKENS, FINAL_ANSWER_TOKENS),
        StepUsage("answer_checker", 0, 0, 0),
        StepUsage("user_clarification", 0, 0, 0),
    ]


def price(model: Dict[str, Any], step_usage: StepUsage, with_thinking: bool, from_2027: bool = False) -> float:
    """
    USD for the calls of one step with one model.
    A model that counts its reasoning inside the output (`output_multiplier` > 1, like gpt-oss) always pays for it.
    A Gemini model that thinks pays for the thinking only when `with_thinking`.
    """
    factor = 2 if from_2027 and "2027-01-01" in model["price_note"] else 1
    multiplier = model.get("output_multiplier", 1.0)
    thinking = THINKING[step_usage.step] * THINKING_FACTOR.get(model["id"], 0.0) * step_usage.calls if with_thinking else 0
    output = step_usage.output_tokens * multiplier + thinking
    return factor * (step_usage.input_tokens * model["input"] + output * model["output"]) / 1e6


def choice_strongest(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """For every step, the strongest model of its table (the last one rated best, else good)."""
    return {step: best_options(data, step)["strongest"] for step in data["steps"]}


def choice_single(data: Dict[str, Any], model_id: str) -> Dict[str, Dict[str, Any]]:
    model = next(m for m in data["models"] if m["id"] == model_id)
    return {step: model for step in data["steps"]}


def total_row(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    return {key: sum(r[key] for r in rows) for key in ("visible", "thinking", "visible_2027", "thinking_2027")}


def rows_for(choice: Dict[str, Dict[str, Any]], usages: List[StepUsage]) -> List[Dict[str, Any]]:
    rows = []
    for u in usages:
        model = choice[u.step]
        rows.append({
            "step": u.step, "model": model["id"], "calls": u.calls, "input": u.input_tokens, "output": u.output_tokens,
            "visible": price(model, u, False), "thinking": price(model, u, True),
            "visible_2027": price(model, u, False, True), "thinking_2027": price(model, u, True, True),
        })
    return rows


def _money(value: float) -> str:
    return "$0" if value == 0 else f"${value:.4f}" if value < 0.01 else f"${value:.3f}" if value < 1 else f"${value:.2f}"


def markdown(data: Dict[str, Any], actions: int = 5, subactions: int = 5, tool_actions: int = 5) -> str:
    usages = usage(actions, subactions, tool_actions)
    nodes = actions * (1 + subactions)
    total_in, total_out = sum(u.input_tokens for u in usages), sum(u.output_tokens for u in usages)
    scenarios = [
        ("A. The strongest model of each step", choice_strongest(data)),
        ("B. `gemini-3.1-pro-preview` on every step (the strongest model there is)", choice_single(data, "gemini-3.1-pro-preview")),
        ("C. For comparison: `gemini-2.5-flash` on every step (what the agent uses today)", choice_single(data, "gemini-2.5-flash")),
    ]

    lines = [
        f"# Cost of one message with a big plan: {actions} actions x {subactions} subactions = {nodes} actions",
        "",
        "_Generated by `tests/manual/estimate_cost.py --write` from `config/gemini_models.json` and `tests/cost_estimate.py`. "
        "The version that also covers other providers and a budget is `docs/models_per_step_budget.md`._",
        "",
        "## The scenario",
        "",
        f"- {actions} actions, each with {subactions} subactions: **{nodes} actions** in total "
        f"(the limit is 10 subactions per action). {tool_actions} of the subactions use a tool.",
        "- The steps run in this order: triage, planner, safety gate, then one call per action "
        "(the worker, or the tool operator and the data engineer for a tool action), the draft and the editor. "
        "The answer checker and the question step only run when the agent asks the user something, so they cost nothing here.",
        f"- **About {total_in + total_out:,} tokens in {sum(u.calls for u in usages)} calls** ({total_in:,} sent, {total_out:,} answered, "
        "not counting thinking).",
        "",
        "## How the tokens were estimated",
        "",
        "Measured in real runs with gemini-2.5-flash (tokens sent / answered by one call): triage 1,260 / 150, planner 1,600 / "
        f"about {PLANNER_BASE_OUTPUT} + {PLANNER_TOKENS_PER_ACTION} per action, gate 1,130 + {ACTION_REPR} per action / 55, "
        "worker 1,070 / 90 to 900 (depends on what it writes), draft 1,150 + everything it reads, editor 1,090 + the draft.",
        "",
        f"Assumed, not measured: each action writes about {ANSWER_TOKENS} tokens (a parent action {PARENT_ANSWER_TOKENS}), "
        f"the final answer is {FINAL_ANSWER_TOKENS} tokens, a tool result is {TOOL_RESULT_TOKENS} tokens. "
        "The draft writer reads all the outputs, so it is the biggest single call (about 12,000 tokens of input, "
        "which every model here takes).",
        "",
        "**Thinking tokens.** Gemini bills them as output and does not count them in the answer's token count "
        "(they are only in the total: measured). The column \"with thinking\" adds them: per call, what gemini-3.8-flash "
        "was measured to think (triage 489, gate 231, worker 724, draft 344, editor 115; the planner about 1,970 for a "
        "plan this big, twice the measured 985), times a factor per model (2.5 Flash 0.7 as measured, 2.5 Flash-Lite and "
        "3.1 Flash-Lite 0 as measured, 3.5 Flash-Lite 0.1, the other Flash models 1, the Pro models 1.5: these last are guesses). "
        "\"From 2027\" doubles the price of 3.6, 3.7 and 3.8 Flash, as Google announced.",
        "",
        "## The calls of each step",
        "",
        "| Step | Calls | Tokens sent (all calls) | Tokens answered (all calls) |",
        "|---|---|---|---|",
    ]
    for u in usages:
        lines.append(f"| {u.step} | {u.calls} | {u.input_tokens:,} | {u.output_tokens:,} |")

    for title, choice in scenarios:
        rows = rows_for(choice, usages)
        total = total_row(rows)
        lines += ["", f"## {title}", "",
                  "| Step | Model | Calls | Visible | With thinking | From 2027, visible | From 2027, with thinking |",
                  "|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['step']} | `{r['model']}` | {r['calls']} | {_money(r['visible'])} | {_money(r['thinking'])} | "
                         f"{_money(r['visible_2027'])} | {_money(r['thinking_2027'])} |")
        lines.append(f"| **Total for one message** | | {sum(u.calls for u in usages)} | **{_money(total['visible'])}** | "
                     f"**{_money(total['thinking'])}** | **{_money(total['visible_2027'])}** | **{_money(total['thinking_2027'])}** |")
        lines.append(f"| 1,000 messages | | | {_money(total['visible'] * 1000)} | {_money(total['thinking'] * 1000)} | "
                     f"{_money(total['visible_2027'] * 1000)} | {_money(total['thinking_2027'] * 1000)} |")

    rows_a = rows_for(scenarios[0][1], usages)
    top_visible = max(rows_a, key=lambda r: r["visible"])
    top_thinking = max(rows_a, key=lambda r: r["thinking"])
    lines += ["", "## Reading it", "",
              f"- In A, the biggest step is **{top_visible['step']}** ({_money(top_visible['visible'])}) counting only the visible tokens, "
              f"and **{top_thinking['step']}** ({_money(top_thinking['thinking'])}) with the thinking allowance. "
              "The planner is a single call, but it writes the whole plan on the priciest model; "
              "the worker has one call per action, so its cost grows with the size of the plan.",
              "- Changing the model of the biggest steps moves the total the most. To see the options of a step: "
              "`windows\\Scripts\\python.exe tests\\manual\\show_models.py --step=cognitive_worker`.",
              "- Change the size of the plan: `windows\\Scripts\\python.exe tests\\manual\\estimate_cost.py --actions=3 --subactions=2 --tools=0`.",
              ""]
    return "\n".join(lines)
