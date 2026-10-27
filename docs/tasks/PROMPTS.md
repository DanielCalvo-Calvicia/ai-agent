# Prompts to start and resume the build

Two prompts for a Claude Code session in `D:\Snowfactory\Programas\Python\ai-agent`, on the branch `feature_dynamics_mcp`. Paste one as the first message. They follow the protocol in [README.md](README.md) and keep progress in the task files, so any session can continue where another stopped.

The documents (questionnaires, tasks) are **not committed yet**: the new session must run in this same folder so it sees them.

---

## 1. START (the first task, or any task)

```text
You are going to build epic T-01 of this repository (use the MCP tools of dynamics_microservice from ai-agent), one task at a time, following the task files exactly. Answer me in the language I write to you; code, comments and documents in English.

## Read first, in this order, before touching anything
1. CLAUDE.md (the rules and the table "every change updates the documentation").
2. docs/tasks/README.md: the structure, the execution protocol (section 2), the definition of done (section 3), the facts (section 4) and the board (section 5).
3. docs/tasks/ORDER.md: the order of the tasks and their state.
4. docs/tasks/T-01_dynamics-mcp/T-01_dynamics-mcp.md (the epic) and T-01.1_decisions.md (the Resolution: every decision of the maintainer is there).
5. The task you are about to do, and the documents it names. Then docs/architecture/architecture.md section 10 and the files of infrastructure/outbound/mcp/.
6. The questionnaires in docs/setup/questionnaires/ (Q01 to Q04) only when a task says "Qxx-n" and you need the exact words of an answer.
7. Read-only reference, never modify it: D:\Snowfactory\Programas\GO\dynamics_microservice (docs/api/mcp.md and docs/decisions/ADR-025-mcp-inbound-adapter.md).

## How to work
- Pick the first task of ORDER.md whose state is Todo and whose dependencies are Done. Start with T-01.2 unless ORDER.md says otherwise. Tell me which task you chose and why, then do only that task.
- Create or change only the files listed under Files of the task (tests included). If you need another file, folder or dependency, update the task first and tell me.
- Everything goes on the branch feature_dynamics_mcp. Never create another branch. Never commit, push or open a pull request unless I ask. Never run git commands that change history.
- The Go project is read-only. Business Central is read-only. Nothing in this plan writes to it.
- NEVER call a real LLM, a real MCP server of the maintainer, or anything that costs money. Tests use scripted LLMs and local fake servers only. T-01.9 (the first real run) is run by the maintainer, not by you.
- No secret, host, tenant, environment, company or customer code in code, tests, fixtures, prompts or documents: placeholders only. Never read, print or copy the values of .env.
- No log line, metric or span may hold a tool argument or a tool answer.
- Match the surrounding code: comment density, naming, idiom. Keep the layers: domain imports nothing of the application; application never imports infrastructure; the transport lives in infrastructure/outbound/mcp/.
- The Windows venv "windows" does not exist yet. When a task needs it (T-01.2 does, to run the tests), create it with Python 3.14 (py -3.14 -m venv windows, then pip install -r requirements.txt, which also installs ../shared-logging in editable mode). ASK ME once more right before installing anything.
- A change to a prompt, schema, model or message format changes tests/golden/flow_golden.json: read the diff first, then regenerate on purpose (UPDATE_GOLDEN=1).
- Before using any function of a library (for example the Streamable HTTP client of the mcp package), check its real signature in the installed version; do not guess.

## When a task is done
1. Run the Verification of the task and the baseline of docs/tasks/README.md section 3 (python -m pytest tests, python scripts/split_schemas.py). Show me the real output. If something fails, say so and fix it; never mark a task done with a failing check.
2. Update, in the same piece of work: the task file (Status, Notes with any deviation or new fact), the board in docs/tasks/README.md section 5, docs/tasks/ORDER.md (state and date), the epic file if its table changes, and every document of the table in CLAUDE.md that the change touches (configuration, architecture, requirements, security, monitoring, api). Check that the links resolve.
3. Report: what you built, the files you changed, the checks you ran and their result, what you could not verify, and which task is next. Then STOP and wait for me. Do not start the next task on your own.

## If something does not match
If a task contradicts the code, a questionnaire answer or the Go documents, or an answer is ambiguous, do not guess: stop, say exactly what conflicts, and ask me. Record the answer in the task's Notes.
```

---

## 2. RESUME (a later session)

```text
You are continuing epic T-01 of this repository (use the MCP tools of dynamics_microservice from ai-agent). Answer me in the language I write to you; code and documents in English.

Read, in this order: CLAUDE.md; docs/tasks/README.md (sections 2, 3 and 5); docs/tasks/ORDER.md; the epic file; the Resolution of T-01.1; then run `git status` and `git log --oneline -5` on the branch feature_dynamics_mcp.

Find the first task of ORDER.md that is Todo or In progress. If a task is In progress, read its Notes and the diff of the files it lists, tell me what is done and what is left, and continue it. Otherwise pick the first Todo task whose dependencies are Done.

Follow the same rules as the START prompt of docs/tasks/PROMPTS.md (one task at a time, only the files the task lists, one branch feature_dynamics_mcp, no commit or push unless I ask, nothing that calls a real LLM or a real server, no secrets or hosts, no tool arguments or answers in logs, update the task file, the board, ORDER.md and the documents of the CLAUDE.md table, show real test output, then STOP and report).

If the venv "windows" is missing, create it with Python 3.14 as the START prompt says, and ask me right before installing.
```
