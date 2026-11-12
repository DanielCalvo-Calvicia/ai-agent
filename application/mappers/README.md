# application/mappers/

The conversions at the two edges of the application, so that `infrastructure/` never builds or reads a domain object itself.

| Folder | What it is |
|---|---|
| [`inbound/`](inbound/README.md) | HTTP DTOs <-> what a run works with. |
| [`outbound/`](outbound/README.md) | What an outbound adapter gives or needs <-> domain objects. |
