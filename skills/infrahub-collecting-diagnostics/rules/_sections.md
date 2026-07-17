# Infrahub Diagnostics Collector - Rule Sections

1. **Workflow (workflow-)** -- CRITICAL. Two
   user-gates: review-before-sharing and hand-off.

2. **Install (install-)** -- HIGH. Verify the
   `infrahub-collect` binary is present before
   installing; install per OS/arch when it's missing.

3. **Detection (deployment-)** -- HIGH. Defer to
   `infrahub-collect environment detect`/`list`;
   disambiguate with `--project`/`--k8s-namespace`.

4. **Create flags (create-)** -- HIGH. Symptom-to-flag
   mapping for `infrahub-collect create`
   (`--benchmark`, `--include-queries`,
   `--include-backup`, etc.).

5. **Collection (collection-)** -- CRITICAL. Read-only
   tool and read-only surrounding commands. No
   mutations, no destructive actions.

6. **Bundle (bundle-)** -- HIGH. The tool's on-disk
   `bundle/` layout — reference only, the skill does
   not build it by hand.

7. **Review (review-)** -- CRITICAL. Masking covers
   key names only; user reviews `bundle/logs/` and
   `bundle/server/` before sharing.

8. **Cross-linking (cross-link-)** -- MEDIUM. At
   workflow end, point users to `infrahub-reporting-
   issues` if they then want to file a public issue.
   Never duplicate that skill's routing.
