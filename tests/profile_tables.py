"""
What an assembled profile is made of and what a full plan costs with it: one table per profile (PR-005 sections 9 and 10, T-05.17).

    explain(agent, "special")            the rows of one profile: step, kind, models and where they come from, tools, prompt, cost
    explain_text(report)                 the same as text (`python scripts/check_agent.py --explain special`)
    profiles_markdown(agent)             docs/models/profiles.md: one section per profile (`python scripts/model_tables.py --profiles`)

The steps, the models and the tools come from the ASSEMBLED profile (its flow, its model resolver, its tool scopes, its prompt
overrides), not from the table of phase names. The cost is an ESTIMATE of one message with a big plan (5 actions x 5 subactions,
5 tool actions: `cost_estimate.usage()`), with the prices of config/*_models.json; a step the estimate has no token model for
(the movement and gesture steps) shows no cost and the total is then partial.
"""
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from application.assembly.model import Agent
from application.runtime.profile.runner import ProfileRunner
from application.support.metrics import SessionMetrics
from application.outbound.ports.llm_ports import LLMOutboundPort
from budget_table import combined
from cost_estimate import usage as plan_usage, price

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "models", "profiles.md")
EXECUTOR_STEPS = ("cognitive_worker", "mcp_operator", "data_engineer")      # run by the action executor, not listed by a flow


class _NoLLM(LLMOutboundPort):
    def is_available(self) -> bool:
        return False

    def ask(self, Payload):
        raise RuntimeError("explain never calls a model")


def steps_of(agent: Agent, name: str) -> List[Tuple[str, bool]]:
    """(step, run by the action executor) in order: the steps of the flow, the executor's three after the executor."""
    steps: List[Tuple[str, bool]] = []
    for step in agent.profile(name).steps:
        steps.append((step, False))
        if step == "action_executor":
            steps += [(child, True) for child in EXECUTOR_STEPS if child in agent.step_defs]
    return steps


def explain(agent: Agent, name: str, mcp_servers: Optional[List[str]] = None, models: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`mcp_servers`: the names of the configured servers (for the tools column); `models`: id -> price entry (the catalog of config/)."""
    profile = agent.profile(name)
    catalog = models if models is not None else {m["id"]: m for m in combined()["models"]}
    runner = ProfileRunner(_NoLLM(), [{"name": n} for n in (mcp_servers or [])], SessionMetrics(), None, agent)
    usages = {u.step: u for u in plan_usage()}
    rows: List[Dict[str, Any]] = []

    for step, by_executor in steps_of(agent, name):
        declaration = agent.step_defs.get(step, {})
        kind = declaration.get("kind", "?")
        row: Dict[str, Any] = {"step": step, "kind": kind, "by_executor": by_executor, "legacy_id": declaration.get("legacy_id"),
                               "models": [], "source": "", "tools": None, "prompt": (declaration.get("prompt") or {}).get("file", ""),
                               "prompt_override": "", "calls": None, "visible": None, "thinking": None}
        if kind != "code":
            from domain.value_objects.llm_request.model import GoogleModels
            default = GoogleModels(declaration["default_models"][0])
            row["models"] = [m.id for m in profile.resolver.models_for(profile.flow_name or "", step, default)]
            row["source"] = profile.resolver.source_for(profile.flow_name or "", step)
            override = profile.prompts.get(step)
            row["prompt_override"] = "+".join(part for part, text in (("replace", override.replace if override else None),
                                                                       ("append", override.append if override else None)) if text)
            if mcp_servers is not None and step in ("project_manager", "mcp_operator"):
                row["tools"] = runner.servers_of(name, "action_executor" if step == "mcp_operator" else step)
            u = usages.get(step)
            model = catalog.get(row["models"][0])
            if u is not None and u.calls and model is not None:
                priced = {**model, "price_note": model.get("price_note", "")}
                row["calls"] = u.calls
                row["visible"], row["thinking"] = price(priced, u, False), price(priced, u, True)
        rows.append(row)

    priced_rows = [r for r in rows if r["visible"] is not None]
    return {
        "profile": name, "flow": profile.flow_name, "hash": profile.profile_hash, "return": profile.default_return,
        "requires": profile.requires, "accepts": profile.accepts, "tested": profile.definition.get("tested"),
        "models": profile.definition.get("models"), "rows": rows,
        "visible": sum(r["visible"] for r in priced_rows), "thinking": sum(r["thinking"] for r in priced_rows),
        "partial": len(priced_rows) < len([r for r in rows if r["kind"] != "code"]),
    }


def _money(value: Optional[float]) -> str:
    return "-" if value is None else "$0" if value == 0 else f"${value:.4f}" if value < 0.01 else f"${value:.3f}" if value < 1 else f"${value:.2f}"


def explain_text(report: Dict[str, Any]) -> str:
    rows = []
    for r in report["rows"]:
        tools = "" if r["tools"] is None else (", ".join(r["tools"]) or "none")
        prompt = r["prompt"] + (f" ({r['prompt_override']})" if r["prompt_override"] else "")
        rows.append((("  " if r["by_executor"] else "") + r["step"], r["kind"], ", ".join(r["models"]) if r["models"] else "plain code",
                     r["source"], tools, prompt))
    header = ("step", "kind", "models (the first answers)", "comes from", "tools", "prompt")
    widths = [max(len(row[i]) for row in rows + [header]) + 2 for i in range(5)]
    lines = [f"profile {report['profile']}: flow {report['flow']}, models {report['models']}",
             f"hash {report['hash']}",
             f"answers with {report['return']}; requires {report['requires'] or 'nothing'}; accepts {report['accepts'] or 'nothing'}; "
             f"tested {report['tested'] or 'never'}", ""]
    for row in [header] + rows:
        lines.append("".join(row[i].ljust(widths[i]) for i in range(5)) + row[5])
    lines += ["", f"cost of one message with a big plan (5 actions x 5 subactions, 5 tool actions; an estimate): "
                  f"{_money(report['visible'])} visible, {_money(report['thinking'])} with thinking"
                  + ("; PARTIAL: some steps have no token estimate or no price" if report["partial"] else "")]
    return "\n".join(lines) + "\n"


def profiles_markdown(agent: Agent, mcp_servers: Optional[List[str]] = None) -> str:
    lines = ["# The profiles: what each is made of and what a full plan costs", "",
             "_Generated by `python scripts/model_tables.py --profiles` from the assembled profiles (`profiles/`, `flows/`, `step_defs/`, "
             "`model_sets/`) and the prices of `config/*_models.json`. Do not edit by hand. The same for one profile, as text: "
             "`python scripts/check_agent.py --explain <profile>`._", "",
             "The cost is an **estimate** of one message with a big plan (5 actions x 5 subactions = 30 actions, 5 tool actions), with the "
             "token model of `tests/cost_estimate.py`. A step with no token model (the movement and gesture steps) or no price shows `-` and "
             "the total of that profile is marked partial. The model of a step is the first of its list (the next ones are the fallback)."]
    for name in sorted(agent.profiles):
        report = explain(agent, name, mcp_servers)
        lines += ["", f"## `{name}`", "",
                  f"- Flow `{report['flow']}`, models `{report['models']}`, answers with `{report['return']}`, "
                  f"requires {', '.join(f'`{r}`' for r in report['requires']) or 'nothing'}, tested {report['tested'] or 'never'}.",
                  f"- Hash of the assembled profile: `{report['hash'][:12]}` (the first 12 characters).", "",
                  "| Step | Kind | Model | Comes from | Tools | Prompt | Calls | Visible | With thinking |", "|---|---|---|---|---|---|---|---|---|"]
        for r in report["rows"]:
            tools = "" if r["tools"] is None else (", ".join(f"`{t}`" for t in r["tools"]) or "none")
            prompt = (f"`{r['prompt']}`" if r["prompt"] else "") + (f" ({r['prompt_override']})" if r["prompt_override"] else "")
            lines.append(f"| {'↳ ' if r['by_executor'] else ''}{r['step']} | {r['kind']} | {('`' + r['models'][0] + '`') if r['models'] else 'plain code'} | "
                         f"{r['source']} | {tools} | {prompt} | {r['calls'] if r['calls'] is not None else '-'} | {_money(r['visible'])} | {_money(r['thinking'])} |")
        lines.append(f"| **Total for one message** | | | | | | | **{_money(report['visible'])}** | **{_money(report['thinking'])}** |"
                     + (" (partial)" if report["partial"] else ""))
    return "\n".join(lines) + "\n"
