# application/mappers/outbound/

Conversions between what an outbound adapter gives or needs and the domain objects.

| File | Contents |
|---|---|
| `response_mapper.py` | `build_response` / `read_response_json`: the model's text or JSON into the domain `Response`, one function per section (moved here from `infrastructure/outbound/llm/` on 2026-11-12: an adapter does not build domain objects). |
