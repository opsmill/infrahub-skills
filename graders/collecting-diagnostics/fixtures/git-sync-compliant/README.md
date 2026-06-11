# Diagnostics bundle — git-sync investigation

Generated: 2026-05-30T12:00:00Z
Problem category: git-sync
Infrahub: 1.9.6 community, docker-compose, 2 task-worker replicas.

See `manifest.yml` for the full table of contents. The
`baseline/` tree captures the canonical environment snapshot;
`category/git-sync/` contains worker-scoped git state and the
repositories GraphQL payload. Flags raised during collection
are in `flags.yml`. All values matching secret patterns have
been replaced — see `redaction-report.txt` for the audit.
