# Common Rules - Rule Sections

These rules apply across multiple Infrahub skills (generators, checks, transforms, object loading). They capture shared gotchas and best practices that are not specific to any single workflow.

1. **Deployment (deployment-)** -- CRITICAL. Git repository integration, CoreRepository vs CoreReadOnlyRepository, local dev setup, worker race conditions, file commit requirements.

2. **Protocols (protocols-)** -- CRITICAL. Protocol files are generated code (`infrahubctl protocols generate`), never edit directly, regenerate after schema changes, supports local schema directory.

3. **Caching (caching-)** -- MEDIUM. Display label caching with parent relationships, batch loading timing issues, no-op mutation workarounds.
