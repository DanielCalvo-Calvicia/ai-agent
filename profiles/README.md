# profiles/

One JSON file per profile: what a client asks for on every request (PR-005, `docs/proposals/PR-005-flows-steps-profiles.md`, section 3.4). A profile names one flow or an ordered list of steps, its models, tools, prompts and inputs. A folder that starts with `_` is not loaded.

Empty until T-05.7. Every file carries `schema_version`; a token is stored as `token_sha256`, never as the token.
