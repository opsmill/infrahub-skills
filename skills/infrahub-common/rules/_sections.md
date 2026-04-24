# Common Rules - Rule Sections

These rules apply across multiple Infrahub skills
(Generators, checks, Transformations, object loading). They
capture shared gotchas and best practices that are not
specific to any single workflow.

1. **Execution (execution-)** -- HIGH. Working discipline
   that applies to every Infrahub artifact: surface
   structural assumptions before generating, produce only
   what was requested, edit existing artifacts surgically,
   verify with the right `infrahubctl` command before
   declaring done.

2. **Deployment (deployment-)** -- CRITICAL. Git repository
   integration, CoreRepository vs
   CoreReadOnlyRepository, local dev setup, worker race
   conditions, file commit requirements.

3. **Protocols (protocols-)** -- CRITICAL. Protocol files
   are generated code (`infrahubctl protocols generate`),
   never edit directly, regenerate after schema changes,
   supports local schema directory.

4. **Connectivity (connectivity-)** -- HIGH. Python
   environment detection (`uv run` / `poetry run` /
   direct), server reachability via `infrahubctl info`,
   offline vs online command awareness, environment
   variable requirements.

5. **Caching (caching-)** -- MEDIUM. Display label caching
   with parent relationships, batch loading timing issues,
   no-op mutation workarounds.
