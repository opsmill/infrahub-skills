# Common Rules - Rule Sections

These rules apply across multiple Infrahub skills
(Generators, checks, Transformations, object loading). They
capture shared gotchas and best practices that are not
specific to any single workflow.

1. **Deployment (deployment-)** -- CRITICAL. Git repository
   integration, CoreRepository vs
   CoreReadOnlyRepository, local dev setup, worker race
   conditions, file commit requirements, recovery from
   partial repository syncs (sticky-state cleanup when an
   import fails mid-pass), and pre-merge dry-run validation
   of `.gql` queries against a live schema (YAML-check
   alone misses GraphQL/schema mismatches).

2. **Protocols (protocols-)** -- CRITICAL. Protocol files
   are generated code (`infrahubctl protocols generate`),
   never edit directly, regenerate after schema changes,
   supports local schema directory.

3. **Connectivity (connectivity-)** -- HIGH. Python
   environment detection (`uv run` / `poetry run` /
   direct), server reachability via `infrahubctl info`,
   offline vs online command awareness, environment
   variable requirements.

4. **Caching (caching-)** -- MEDIUM. Display label caching with parent relationships, batch loading timing issues, no-op mutation workarounds.

5. **Testing (testing-)** -- HIGH. Resources Testing Framework, YAML-driven pytest tests, smoke/unit/integration test kinds, always-create-tests recommendation.
