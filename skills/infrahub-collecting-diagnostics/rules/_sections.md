# Infrahub Diagnostics Collector - Rule Sections

1. **Workflow (workflow-)** -- CRITICAL. User-gate
   semantics, which steps stop for user input,
   what the user can override.

2. **Connection (connection-)** -- CRITICAL. Capture
   Infrahub URL + API token up front, with the
   verbatim privacy notice. Token-decline is a
   supported partial-bundle path; see
   `connection-info-and-token.md`.

3. **Collection (collection-)** -- CRITICAL. Read-only
   command policy. No mutations, no destructive
   actions, no interactive shell access.

4. **Instance contract (infrahubctl-only-)** -- CRITICAL.
   `infrahubctl` is the only contract for probing
   instance state. No `/api/*` curls, no GraphQL
   POSTs, no `docker compose exec`/`kubectl exec`
   into stack containers for cypher-shell, psql,
   rabbitmqctl, neo4j-admin, or env. See
   `infrahubctl-only-for-instance.md`.

5. **Coverage (multi-replica-)** -- CRITICAL. Always
   pull logs and state from every task-worker
   replica, not just the first. Multi-worker race
   conditions hide root cause when only one replica
   is sampled.

6. **Redaction (redaction-)** -- CRITICAL. Two-tier
   policy: Tier 1 auto-redact secrets, Tier 2 user
   review gate for IPs/hostnames/customer data.
   Bundles must be safe to share by default.

7. **Detection (deployment-)** -- HIGH. Order of
   topology detection (Compose -> Kubernetes ->
   local dev -> manual) and per-topology command
   shapes.

8. **Bundle (bundle-)** -- HIGH. On-disk structure
   of the diagnostic bundle. `manifest.yml` schema
   and required fields.

9. **Manifest (manifest-)** -- HIGH. Bug-report-
   template-mirroring fields, version cross-check
   between `infrahubctl version` and `/api/config`
   (only when the user pastes the latter
   themselves).

10. **Flag checks (flag-checks-)** -- HIGH. Flag
    checks are deterministic only — pattern match
    over collected files. Never LLM-judged. Hints,
    not diagnoses.

11. **Cross-linking (cross-link-)** -- MEDIUM. At
    workflow end, point users to `infrahub-reporting-
    issues` if they then want to file a public
    issue. Never duplicate that skill's routing.
