---
title: Testing Transforms
impact: LOW
tags: testing, infrahubctl, commands, rest-api
---

## Testing Transforms

Impact: LOW (reference)

Iterate on transforms locally with
`infrahubctl transform` (Python) or
`infrahubctl render` (Jinja2) before relying on
artifact regeneration in the UI.

### Why it matters

Artifact generation in the proposed-change pipeline
runs after a successful repo sync, which means every
test cycle through the UI is at least a commit, push,
and pipeline wait — and a failing transform shows up
as a generic pipeline failure, not the Python
traceback. Running locally with `infrahubctl` hits
the same SDK path but prints the raw output and any
exception to the terminal, so the iteration loop
shrinks from minutes to seconds. The split between
the two subcommands also matches the two transform
kinds: `transform` exercises the Python class entry
point, `render` exercises the Jinja2 template alone.

### Prerequisites

All commands below require a running Infrahub server.
Verify connectivity first:

```bash
infrahubctl info
```

See
[Server Connectivity Check](../../infrahub-common/rules/connectivity-server-check.md)
for troubleshooting.

### Commands

```bash
# List available transforms
infrahubctl transform --list

# Run a Python transform
infrahubctl transform my_transform device=spine-01

# Render a Jinja2 transform
infrahubctl render my_jinja_transform device=spine-01

# REST API (after deployment)
# Python: GET /api/transform/python/my_transform?device=spine-01
# Jinja2: GET /api/transform/jinja2/my_transform?device=spine-01&branch=main
```

### Debugging Tips

- Test Python transforms with `infrahubctl transform` to see raw output
- Test Jinja2 templates with `infrahubctl render` to see rendered text
- Check that `query` class attribute matches the
  query `name` in `.infrahub.yml`
- Use `print()` in `transform()` during development for data inspection

### Local Render ≠ Deployed Artifact — Two Different Lifecycles

Be explicit about which lifecycle you're testing:

| Lifecycle | What loads | How |
| --------- | ---------- | --- |
| **Local render** | The single transform file you point at | `infrahubctl transform <name>` / `infrahubctl render <name>` reads the file off disk and renders against live server data |
| **Artifact pipeline** | Everything in the registered repo: `queries:`, `jinja2_transforms:`, `python_transforms:`, `artifact_definitions:` | Requires the repo to be registered as a `CoreReadOnlyRepository` (or `CoreRepository`) and synced |

The trap: `infrahubctl object load .` ingests
schema objects and data objects, but it does **not**
ingest queries, transforms, or artifact definitions
— those are repo-lifecycle objects, picked up only
when the repository itself is registered and the
worker pulls from git.

Concretely:

- During iteration: edit `.j2` / `.py` / `.gql`
  files on disk and use `infrahubctl render` /
  `infrahubctl transform` to test. Fast loop, no
  commit needed.
- Before artifacts will appear in the UI: commit
  every file referenced from `.infrahub.yml`, push,
  and either create a `CoreReadOnlyRepository`
  pointing at the repo (one-time setup) or trigger
  a pull on the existing repo. The worker clones
  the committed HEAD; uncommitted changes are
  invisible.

If artifacts don't appear after a repo sync,
inspect the repo status — partial-sync recovery is
covered in
[../../infrahub-common/rules/deployment-partial-sync-recovery.md](../../infrahub-common/rules/deployment-partial-sync-recovery.md).

### Read-Only Repos Don't Auto-Pull on Push

`CoreReadOnlyRepository` is intentionally
read-only — it does **not** poll git or react to
webhook pushes. Pushing a new commit to the
upstream repo does nothing on its own; the repo
stays at its registered ref until someone
explicitly tells Infrahub to advance it. Two
triggers do the job:

```graphql
# GraphQL — pull the latest commit from the configured branch
mutation {
  InfrahubReadOnlyRepositoryImportLastCommit(
    data: { id: "<repo-id>" }
  ) {
    ok
  }
}
```

```bash
# REST — regenerate stale artifacts for a single definition
curl -X POST "$INFRAHUB_ADDRESS/api/artifact/generate/<artifact-definition-id>" \
  -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN"
```

Pick the first when you want the repo to advance
to a new commit (and re-ingest queries, transforms,
artifact definitions). Pick the second when the
repo content is fine but artifact bodies need to
be re-rendered against current data. Without one
of these, "I pushed a fix and the artifact still
shows the old config" is the canonical user
complaint.

Reference: [Infrahub CLI Docs](https://docs.infrahub.app)
