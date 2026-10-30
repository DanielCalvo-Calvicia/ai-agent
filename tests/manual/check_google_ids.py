"""
MANUAL script (T-02.3): one tiny REAL call per Gemini id of the catalog, through the same route the agent uses
(OpenAI-compatible endpoint of GOOGLE_URL, key of GOOGLE_API_KEY). It proves an id is accepted by this key, not that the
model is good at a step. A call is a few tokens: free on the free tier, a fraction of a cent on a billed key. Ask first.

    windows/Scripts/python.exe tests/manual/check_google_ids.py --dry-run          which ids, which variables are set (names only), NO call
    windows/Scripts/python.exe tests/manual/check_google_ids.py --list             which ids the endpoint lists for this key (free: no tokens; listed is NOT proof)
    windows/Scripts/python.exe tests/manual/check_google_ids.py                    one call per id of GoogleModels
    windows/Scripts/python.exe tests/manual/check_google_ids.py --ids=gemini-3.8-flash,gemini-4-argon
    windows/Scripts/python.exe tests/manual/check_google_ids.py --provider=anthropic   one call per id of AnthropicModels (ANTHROPIC_API_KEY; no listing, no probe)
    windows/Scripts/python.exe tests/manual/check_google_ids.py --probe=10         also N calls in a row to the two default models
                                                                                   (--pause=<seconds> between them, default 0;
                                                                                    --timeout=<seconds> per call, default 60)

Prints a table and writes tests/output/check_google_ids.md. Never prints the key (it is masked in any error text) and does
not edit any file: copy the result into `api_check` of config/gemini_models.json (and the rate-limit result into the notes of T-02.3).
Exit code 1 when an id failed. Not collected by pytest.
"""
import os
import sys
import threading
import time
from datetime import date

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

from ai_sdk import generate_text

from domain.value_objects.llm_request.model import AnthropicModels, GoogleModels, get_selected_model
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.provider_models import resolve_provider_model

PROMPT = "Reply with the single word OK."
DEFAULT_MODELS = ("gemini-3.1-flash-lite", "gemini-3.6-flash")        # the two code defaults (profile google_free)
REPORT = os.path.join(PROJECT_ROOT, "tests", "output", "check_google_ids.md")   # --provider=anthropic writes check_anthropic_ids.md


def option(argv, name, default=None):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), default)


def call(config, model_id, timeout):
    """One tiny call, abandoned after `timeout` seconds (the client retries a 503 and would wait minutes; the thread is a daemon)."""
    box = []
    worker = threading.Thread(target=lambda: box.append(_call(config, model_id)), daemon=True)
    started = time.perf_counter()
    worker.start()
    worker.join(timeout)
    if box:
        return box[0]
    return False, time.perf_counter() - started, "-", f"no answer in {timeout:g} s (Google may be answering 503 \"high demand\" and the client retrying)"


def listed(config):
    """The ids the endpoint lists for this key. Free: no tokens. Returns (status text, set of ids)."""
    try:
        reply = httpx.get(config.google_url.rstrip("/") + "/models", headers={"Authorization": "Bearer " + config.google_api_key}, timeout=30)
        if reply.status_code != 200:
            return f"HTTP {reply.status_code}", set()
        return "ok", {m["id"].replace("models/", "") for m in reply.json().get("data", [])}
    except Exception as error:
        return f"{type(error).__name__}", set()


def _call(config, model_id):
    """Returns (ok, seconds, tokens text, what came back or the error, with the key masked)."""
    started = time.perf_counter()
    try:
        model = resolve_provider_model(get_selected_model(model_id), config, {"max_tokens": 200})
        result = generate_text(model=model, prompt=PROMPT)
        usage = result.usage.model_dump() if result.usage else {}
        prompt, answered, total = (usage.get(k, 0) or 0 for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
        thinking = max(total - prompt - answered, 0)
        return True, time.perf_counter() - started, f"{prompt} sent, {answered} answered, {thinking} thinking", (result.text or "").strip()[:40]
    except Exception as error:
        text = f"{type(error).__name__}: {error}".replace("\n", " ")
        for key in (config.google_api_key, config.anthropic_api_key):
            if key:
                text = text.replace(key, "***")
        return False, time.perf_counter() - started, "-", text[:300]


def main(argv):
    config = VercelAIConfig.from_env()
    ids = option(argv, "--ids")
    anthropic = option(argv, "--provider", "google") == "anthropic"
    ids = [i.strip() for i in ids.split(",")] if ids else [m.value for m in (AnthropicModels if anthropic else GoogleModels)]
    probe = int(option(argv, "--probe", "0"))
    pause = float(option(argv, "--pause", "0"))
    timeout = float(option(argv, "--timeout", "60"))

    def state(value):
        # a value still written <LIKE_THIS> (the placeholders of .env) is not a value
        return "MISSING" if not value else "PLACEHOLDER" if value.strip().startswith("<") else "set"

    states = ({"ANTHROPIC_API_KEY": state(config.anthropic_api_key)} if anthropic
              else {"GOOGLE_API_KEY": state(config.google_api_key), "GOOGLE_URL": state(config.google_url)})
    missing = [name for name, value in states.items() if value != "set"]
    print("   ".join(f"{name}: {value}" for name, value in states.items()))
    print("ids:", ", ".join(ids), f"| probe: {probe} calls each to {', '.join(DEFAULT_MODELS)}" if probe else "")
    if "--dry-run" in argv:
        print("dry run: no call was made")
        return 0
    if missing:
        print("give", " and ".join(missing), "a real value in .env or the environment first")
        return 2

    if not anthropic:
        status, known = listed(config)
        print(f"models listed by the endpoint for this key: {status}, {len(known)} ids (free, no tokens)")
        for model_id in ids:
            print(f"  {model_id:26} {'listed' if model_id in known else 'NOT listed'}")
        if "--list" in argv:
            return 0

    lines = [f"# check_google_ids ({date.today().isoformat()})", "",
             "One call per id (prompt: 'Reply with the single word OK.'). Proves the id is accepted by the key, nothing more.", "",
             "| id | result | seconds | tokens | answer or error |", "|---|---|---|---|---|"]
    failed = 0
    for model_id in ids:
        ok, seconds, tokens, text = call(config, model_id, timeout)
        failed += 0 if ok else 1
        print(f"{'ok    ' if ok else 'FAILED'} {model_id:26} {seconds:5.1f}s  {tokens:34} {text}", flush=True)
        lines.append(f"| {model_id} | {'answered' if ok else 'FAILED'} | {seconds:.1f} | {tokens} | {text} |")

    if probe and not anthropic:
        lines += ["", f"## {probe} calls in a row to each default model (pause {pause:g} s)", "", "| id | answered | refused | first error |", "|---|---|---|---|"]
        for model_id in DEFAULT_MODELS:
            answered, first_error = 0, ""
            for _ in range(probe):
                ok, _, _, text = call(config, model_id, timeout)
                answered += 1 if ok else 0
                first_error = first_error or ("" if ok else text)
                time.sleep(pause)
            print(f"probe  {model_id:26} {answered}/{probe} answered  {first_error}", flush=True)
            lines.append(f"| {model_id} | {answered} | {probe - answered} | {first_error} |")

    report = REPORT.replace("google", "anthropic") if anthropic else REPORT
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("written:", report)
    return 1 if failed else 0


sys.exit(main(sys.argv[1:]))
