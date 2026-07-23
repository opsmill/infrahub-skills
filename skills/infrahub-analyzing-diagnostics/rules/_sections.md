# Infrahub Diagnostics Analyzer - Rule Sections

1. **Workflow (workflow-)** -- CRITICAL. Ask the
   user for the bundle location (never deduce it),
   read `bundle_information.json` before any log —
   collection failures are findings, not gaps — and
   anchor the deployment context (version, topology,
   replicas) before triage; the version is what
   turns issue matches into conclusions.

2. **Triage (triage-)** -- CRITICAL. Sweep every
   service's logs for the known signal classes
   (tracebacks, ERROR/CRITICAL, panics, OOM,
   connection failures); treat `*.previous.log` as
   restart evidence and read its tail. Evaluate
   benchmark results when present; for performance
   symptoms without them, recommend a `--benchmark`
   bundle (single-CPU score, Neo4j/PostgreSQL
   storage IOPS).

3. **Correlation (correlate-)** -- HIGH. Group raw
   signals by timestamp and causal chain into
   incidents; distinguish root errors from cascade
   errors before reporting.

4. **Issue matching (match-)** -- HIGH. Build GitHub
   search keys from the stable parts of a traceback
   (exception class, normalized message, innermost
   Infrahub frame); strip volatile tokens; search
   `opsmill/infrahub` with `--state all`.

5. **Reporting (report-)** -- CRITICAL. Every finding
   cites a bundle path plus quoted excerpt; unknowns
   are stated as unknowns, never papered over.

6. **Scope (scope-)** -- CRITICAL. Analysis is
   read-only: no deployment mutations, no restarts,
   no fixes applied. Recommendations live in the
   report.

7. **Cross-linking (cross-link-)** -- MEDIUM. No
   bundle → `infrahub-collecting-diagnostics`;
   filing or commenting on an issue →
   `infrahub-reporting-issues`. Never `gh issue
   create` from this skill.
