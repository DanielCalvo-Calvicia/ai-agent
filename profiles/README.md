# profiles/

One JSON file per profile: what a client asks for (PR-005, `docs/proposals/PR-005-flows-steps-profiles.md`, section 3.4). A profile names one flow, its models
(a model set or an ordered list), its MCP servers and the inputs it accepts. A folder that starts with `_` is not loaded.

| Profile | Flow | Models (set) | MCP servers | Token |
|---|---|---|---|---|
| `identification` | the triage alone; answers with the whole `Response` (`default_return: full`) | `proven` | none | yes |
| `chat` | `conversation`: draft writer, editor; reads the classification (inputs) | `claude_haiku` | none | yes |
| `special` | triage, plan, check, execute, write, edit | `claude_mixed` | every configured server | yes |
| `dynamics` | the same steps as `special` | `claude_mixed` | only `dynamics_microservice` | yes |
| `default` | the `special` flow; what a request with no profile gets | `proven` | **none** | no |
| `movement` | motion planner, motion validator | `proven` | none | yes |
| `gesture` | emotion reader, gesture builder; input: the reply | `proven` | none | yes |

- `tools`: `{"servers": [...], "tools": ["server.tool", ...]}`; no `tools` is no limit, `{"servers": []}` is no tool. A flow file, a step of a flow file, `flows.<flow>.tools` and `overrides.<step>.tools` can narrow it: a step may use only what every level that is set allows (T-05.13; `docs/architecture/architecture.md` section 4.2).
- `token_sha256` holds a **placeholder** (64 zeros: no token has this SHA-256). Replace it with the SHA-256 of the real token of each profile before a client can use it; the token itself is never written in a file. Nothing checks a token yet (T-05.9).
- `_unverified/` holds the ten generic profiles of the old model tables on the `default` flow. They are not loaded until each is tested with the real-run command (T-05.17) and the maintainer keeps it.
- Until the request carries the profile (T-05.9) the service runs `default` for every message.
- Every file carries `schema_version`. `scripts/check_agent.py` checks all of them.
