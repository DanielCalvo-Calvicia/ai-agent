# shared/schemas/

No SDK is imported here.

| File | Contents |
|---|---|
| `anthropic_schema.py` | Turns a step's JSON Schema into the subset Anthropic's strict structured output accepts (`additionalProperties: false`, unsupported keywords removed, recursive actions unrolled to 3 levels, the open `parameters` of a tool call as JSON text). Only Claude models use it (ADR-013). `anthropic_schema_problems` reports what it would cut in a custom schema. |
