# Common Rules - Rule Sections

These rules apply across multiple Infrahub skills
(Generators, checks, Transformations, object loading). They
capture shared gotchas and best practices that are not
specific to any single workflow.

1. **Workflow — branch-first (workflow-)** -- CRITICAL. Branch-first data
   CRUD: default to a dedicated branch (not the default
   branch, `main` by convention) for any
   create/update/delete — object loads, MCP writes,
   generator runs, SDK mutations — so mistakes are a branch
   discard instead of a per-object cleanup, and changes go
   through proposed-change review.

2. **Deployment (deployment-)** -- CRITICAL. Git repository
   integration, CoreRepository vs
   CoreReadOnlyRepository, local dev setup, worker race
   conditions, file commit requirements, and recovery
   from partial repository syncs (sticky-state cleanup
   when an import fails mid-pass).

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

6. **Testing (testing-)** -- HIGH. Resources Testing
   Framework, YAML-driven pytest tests, smoke/unit/integration
   test kinds, always-create-tests recommendation.

7. **Workflow — information priority (workflow-)** -- MEDIUM. How to navigate the
   loaded skill content: information-source priority —
   consult the active skill's rules and references, then the
   shared `infrahub-common/` references, before reaching for
   external docs or a web search.
