# Infrahub Diagnostics Collector - Rule Sections

1. **Workflow (workflow-)** -- CRITICAL. User-gate
   semantics, which steps stop for user input,
   what the user can override.

2. **Collection (collection-)** -- CRITICAL. Read-only
   command policy. No mutations, no destructive
   actions, no interactive shell access.

3. **Coverage (multi-replica-)** -- CRITICAL. Always
   pull logs and state from every task-worker
   replica, not just the first. Multi-worker race
   conditions hide root cause when only one replica
   is sampled.

4. **Redaction (redaction-)** -- CRITICAL. Two-tier
   policy: Tier 1 auto-redact secrets, Tier 2 user
   review gate for IPs/hostnames/customer data.
   Bundles must be safe to share by default.

5. **Detection (deployment-)** -- HIGH. Order of
   topology detection (Compose -> Kubernetes ->
   local dev -> manual) and per-topology command
   shapes.

6. **Bundle (bundle-)** -- HIGH. On-disk structure
   of the diagnostic bundle. `manifest.yml` schema
   and required fields.

7. **Manifest (manifest-)** -- HIGH. Bug-report-
   template-mirroring fields, version cross-check
   between `infrahubctl version` and `/api/config`.

8. **Flag checks (flag-checks-)** -- HIGH. Flag
   checks are deterministic only — pattern match
   over collected files. Never LLM-judged. Hints,
   not diagnoses.

9. **Cross-linking (cross-link-)** -- MEDIUM. At
   workflow end, point users to `infrahub-reporting-
   issues` if they then want to file a public
   issue. Never duplicate that skill's routing.
