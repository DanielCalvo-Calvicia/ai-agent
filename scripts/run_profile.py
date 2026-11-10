"""
Runs the fixed set of messages (tests/manual/profile_messages.json) on a profile with the REAL models, saves the answers in
tests/output/ and writes `tested: <date>` in the profile (PR-005 section 10, Q06-27, Q08-5, T-05.17).

    python scripts/run_profile.py <profile>                     asks before it runs: it costs money (a few cents per profile)
    python scripts/run_profile.py <profile> --yes               does not ask
    python scripts/run_profile.py <profile> --mock              a scripted model, no cost, no keys: for the tests of this script
    python scripts/run_profile.py <profile> --root <dir>        another folder with the same layout (profiles/, flows/, ...)
    python scripts/run_profile.py <profile> --messages <file>   another set of messages
    python scripts/run_profile.py <profile> --label before      the report is named ..._<date>_before.md, so a change is run before and after (T-06)

It sends each message to the profile the way the service does. A profile that needs inputs (`chat` needs the classification) first
gets them from the `identification` profile, and a profile that needs a `reply` (`gesture`) gets the message as the reply. It
checks that every message got an answer; whether the answers are GOOD is for a person to read in the saved file, which lists the `points` of
each message as boxes to tick. A message with a `then` makes the profile ask the user and sends the answer as the next message of the same run.
The note `tested: <date>` is written only when every message got an answer, and it is not part of the profile hash.
Keys come from .env (never printed); the Dynamics message needs the Dynamics service running.
"""
import datetime
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests"))

from application.engine.assemble import Agent, assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.profile_inputs import read_inputs
from application.engine.state.response_json import response_to_json
from application.inbound.dto.message import TextRequestDTO
from application.service.message_flow_service import MessageFlowService
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.llm.response_mapper import read_response_json
from infrastructure.outbound.mcp.config import SUPPORTED_TYPES, load_mcp_configs, load_tool_snapshot
from infrastructure.outbound.usage.prices import cost_usd, load_prices

DEFAULT_MESSAGES = os.path.join(PROJECT_ROOT, "tests", "manual", "profile_messages.json")


def load_agent(root: str) -> Agent:
    agent = assemble(build_snapshot(FileConfigSource(root)), mcp_servers=load_tool_snapshot(os.path.join(root, "mcps")),
                     schema_rules={"anthropic": anthropic_schema_problems})
    agent.raise_on_errors()
    return agent


def messages_for(profile: str, path: str = DEFAULT_MESSAGES) -> List[Dict[str, Any]]:
    """The messages of the fixed set that make sense for this profile."""
    with open(path, encoding="utf-8") as f:
        messages = json.load(f)["messages"]
    return [m for m in messages if not m.get("profiles") or profile in m["profiles"]]


def points_for(item: Dict[str, Any], profile: str) -> List[str]:
    """What a good answer of this profile to this message must contain (`points_for` replaces `points` for a profile that answers something else)."""
    return list(item.get("points_for", {}).get(profile) or item.get("points") or [])


def classified_as(response) -> str:
    """What the triage decided, in one line (a profile that answers with no text, `identification`, would show nothing otherwise): the domain, the
    type and complexity, the next step and the questions it asks. Only classification fields, never the user's goal text."""
    if response is None:
        return ""
    data = response_to_json(response)
    category, step = data.get("task_category") or {}, data.get("next_step") or {}
    if not category:
        return ""
    asks = "; ".join(step.get("requested_user_input") or [])
    name = lambda value: str(getattr(value, "value", value))        # a str enum prints as `Domains.SYSTEM`: its value is the word
    return (f"domain={name(category.get('domain'))}, type={name(category.get('type'))}, complexity={name(category.get('complexity'))}, "
            f"next_step={name(step.get('status'))}" + (f", asks: {asks}" if asks else ""))


def run_message(agent: Agent, adapter, mcp_list: list, mcp_tools, cost_of, profile_name: str, message: str,
                then: Optional[str] = None) -> Dict[str, Any]:
    """One message through one profile: what it answered, how many calls, tokens and USD it took (the `identification` it needs included).
    With `then` (the user's answer to a question) the run that paused is resumed with it, as the next message of the same session."""
    profile = agent.profile(profile_name)
    services, started = [], time.time()

    def service(name: str, inputs: Optional[dict] = None) -> MessageFlowService:
        made = MessageFlowService(outbound_port=adapter, mcp_list=mcp_list, mcp_tools=mcp_tools, agent=agent, profile=name,
                                  inputs=inputs or {}, client="run_profile", cost_of=cost_of)
        services.append(made)
        return made

    def text(made: MessageFlowService):
        return made.text(TextRequestDTO(user_id="run_profile", session_id="run_profile", content=message))

    values: dict = {}
    if profile.requires:
        if profile.requires == ["reply"]:
            values = read_inputs(profile, {"reply": message}, read_response_json)
        else:
            identification = service("identification")
            text(identification)
            values = read_inputs(profile, response_to_json(identification.last_response), read_response_json)
    answering = service(profile_name, values)
    result = text(answering)
    follow = None
    if then is not None and answering.paused_run is not None:
        resumed = MessageFlowService(outbound_port=adapter, mcp_list=mcp_list, mcp_tools=mcp_tools, agent=agent, profile=profile_name,
                                     paused=answering.paused_run, client="run_profile", cost_of=cost_of)
        services.append(resumed)
        follow = resumed.text(TextRequestDTO(user_id="run_profile", session_id="run_profile", content=then))
    costs = [s.metrics.message_cost() for s in services if s.metrics.message_cost() is not None]
    return {"classified": classified_as(answering.last_response), "answer": result.content, "movements": len(result.movements), "gesture": result.gesture, "awaiting": result.awaiting_user_input,
            "then_ran": follow is not None, "then_answer": follow.content if follow else "",
            "then_movements": len(follow.movements) if follow else 0, "then_awaiting": follow.awaiting_user_input if follow else False,
            "calls": sum(s.metrics.totals.requests for s in services), "tokens": sum(s.metrics.totals.total for s in services),
            "cost_usd": sum(costs) if costs else None, "seconds": round(time.time() - started, 1), "error": ""}


def run_all(agent: Agent, adapter, mcp_list: list, mcp_tools, cost_of, profile_name: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for item in messages:
        try:
            then = (item.get("then") or {}).get("message")
            outcome = (run_message(agent, adapter, mcp_list, mcp_tools, cost_of, profile_name, item["message"], then=then) if then
                       else run_message(agent, adapter, mcp_list, mcp_tools, cost_of, profile_name, item["message"]))
        except Exception as error:                         # a failed message is reported, the others still run
            outcome = {"classified": "", "answer": "", "movements": 0, "gesture": False, "awaiting": False, "calls": 0, "tokens": 0, "cost_usd": None,
                       "then_ran": False, "then_answer": "", "then_movements": 0, "then_awaiting": False, "seconds": 0, "error": f"{type(error).__name__}: {error}"[:300]}
        results.append({**item, "profile": profile_name, **outcome})
        print(f"  {item['id']:<10} {'ERROR ' + outcome['error'] if outcome['error'] else 'answered'}  "
              f"{outcome['calls']} calls, {outcome['tokens']} tokens, {outcome['seconds']} s")
    return results


def report_path(root: str, profile_name: str, date: str, label: str = "") -> str:
    return os.path.join(root, "tests", "output", f"profile_run_{profile_name}_{date}" + (f"_{label}" if label else "") + ".md")


def write_report(root: str, profile_name: str, date: str, results: List[Dict[str, Any]], models: Any, mock: bool, label: str = "") -> str:
    path = report_path(root, profile_name, date, label)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    total_cost = sum(r["cost_usd"] for r in results if r["cost_usd"] is not None)
    lines = [f"# Profile `{profile_name}`: run of {date}" + (" (a scripted model: not a real run)" if mock else ""), "",
             f"- Models: `{models}`. Messages: {len(results)}. Calls: {sum(r['calls'] for r in results)}. "
             f"Tokens: {sum(r['tokens'] for r in results):,}. Cost: ${total_cost:.4f}.",
             "- Read each answer against what it must contain and tick the boxes (`[x]`): that judgement is a person's, the script only checks that an answer came back.",
             "- Compare a run with the one before it message by message: better, the same or worse; a change that is worse is reverted (T-06).", ""]
    for r in results:
        lines += [f"## {r['id']}", "", f"**Message:** {r['message']}", "", "**Must contain:**", ""]
        lines += [f"- [ ] {point}" for point in points_for(r, r["profile"])] + [""]
        lines += [f"**Answer:** {r['answer'] or '(none)'}" + (f"  \nMovements: {r['movements']}" if r["movements"] else "")
                  + ("  \nA gesture." if r["gesture"] else "") + ("  \nAsked the user a question." if r["awaiting"] else ""), ""]
        if r.get("classified"):
            lines += [f"**Classified as:** {r['classified']}", ""]
        then = r.get("then")
        if then:
            lines += [f"**The user answers:** {then['message']}", ""]
            if r["then_ran"]:
                lines += ["**Must contain:**", ""] + [f"- [ ] {point}" for point in then.get("points", [])] + [""]
                lines += [f"**Answer:** {r['then_answer'] or '(none)'}" + (f"  \nMovements: {r['then_movements']}" if r["then_movements"] else "")
                          + ("  \nAsked the user a question again." if r["then_awaiting"] else ""), ""]
            else:
                lines += ["**The profile did not ask the user a question, so the answer was not sent** (the first answer is judged on its own).", ""]
        lines += [f"{r['calls']} calls, {r['tokens']:,} tokens, {r['seconds']} s" + (f", ERROR: {r['error']}" if r["error"] else ""), ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return path


def write_note(root: str, profile_name: str, date: str) -> str:
    """`tested: <date>` in the profile file (its line endings are kept)."""
    path = os.path.join(root, "profiles", f"{profile_name}.json")
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8")
    data = json.loads(raw)
    data["tested"] = date
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with open(path, "wb") as f:
        f.write((text.replace("\n", "\r\n") if "\r\n" in raw else text).encode("utf-8"))
    return path


def confirm(agent: Agent, profile_name: str, count: int) -> bool:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests"))
    from profile_tables import explain
    report = explain(agent, profile_name, [])
    print(f"Profile {profile_name} (models {report['models']}): {count} messages on the REAL models. A full plan costs about "
          f"${report['visible']:.3f} by the estimate; these messages are small, a few cents in all.")
    if not sys.stdin.isatty():
        print("Not an interactive terminal: pass --yes to run without asking.")
        return False
    return input("Run it? [y/N] ").strip().lower() in ("y", "yes")


def real_services(root: str):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root, ".env"), override=False)
    from infrastructure.outbound.llm.config import VercelAIConfig
    from infrastructure.outbound.llm.vercel import VercelAIAdapter
    from infrastructure.outbound.mcp.client_manager import MCPClientManager, quiet_client_libraries
    from infrastructure.outbound.mcp.config import load_supported_mcp_configs
    from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
    quiet_client_libraries()
    mcp_list = load_supported_mcp_configs(os.path.join(root, "mcps"))
    executor = MCPToolExecutor(MCPClientManager(mcp_list))
    return VercelAIAdapter(Config=VercelAIConfig.from_env(tool_executor=executor)), mcp_list, executor


def main(argv: List[str]) -> int:
    names = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--root", "--messages", "--date", "--label"))]
    if len(names) != 1:
        print(__doc__)
        return 2
    profile_name = names[0]

    def option(flag: str, default: Optional[str] = None) -> Optional[str]:
        return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else default

    root = os.path.abspath(option("--root", PROJECT_ROOT))
    date = option("--date", datetime.date.today().isoformat())
    mock = "--mock" in argv
    agent = load_agent(root)
    if profile_name not in agent.profiles:
        print(f"error: no profile {profile_name!r}. Profiles: {', '.join(sorted(agent.profiles))}")
        return 1
    messages = messages_for(profile_name, option("--messages", DEFAULT_MESSAGES))
    if not messages:
        print(f"error: no message of the set applies to the profile {profile_name!r}")
        return 1

    if mock:
        from test_flow_golden import ScriptedLLM
        emotion = {"emotion_reader_phase30_response_format": {"emotion": "joy", "intensity": 4, "improvised": []}}      # the scripted model answers it
        adapter, mcp_list, executor, prices = ScriptedLLM(overrides=emotion), [], None, {}
    else:
        if "--yes" not in argv and not confirm(agent, profile_name, len(messages)):
            print("Nothing was run.")
            return 2
        adapter, mcp_list, executor = real_services(root)
        prices = load_prices(os.path.join(root, "config"))

    results = run_all(agent, adapter, mcp_list, executor, lambda m, p, c, t: cost_usd(prices, m, p, c, t), profile_name, messages)
    path = write_report(root, profile_name, date, results, agent.profile(profile_name).definition.get("models"), mock, option("--label", "") or "")
    print(f"answers saved: {path}")
    if any(r["error"] for r in results):
        print("some messages failed: the profile was NOT marked as tested")
        return 1
    print(f"profile marked as tested: {write_note(root, profile_name, date)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
