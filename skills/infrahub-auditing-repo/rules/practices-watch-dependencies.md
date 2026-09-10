---
title: practices-watch-dependencies
impact: MEDIUM
tags: audit, practices, watch, transforms, generators, regeneration, fingerprint
---

# Rule: practices-watch-dependencies

**Severity**: MEDIUM
**Category**: Best Practices

## What It Checks

Every `python_transforms`, `generator_definitions`, and
`jinja2_transforms` entry in `.infrahub.yml`, against the
dependency closure Infrahub actually computes for it. Four
findings, in descending order of cost:

1. A `python_transforms` or `generator_definitions` entry
   with **no `watch` key at all**.
2. A `watch.files` list that **omits a dependency** the entry
   really has — a first-party import or a file read at
   runtime.
3. A `watch.files` entry that **matches no Git-tracked file**.
4. `watch` on a section that **rejects it**, or in a shape the
   model rejects.

## Why it matters

Infrahub stores a dependency closure per definition at import
time. Inside a proposed change, a changed file re-renders that
definition's artifacts — or re-runs the Generator's instances —
only when the file is in that closure.

For Python, the closure that gets detected is **the entry file
at `file_path` and nothing else**. Imports are never followed,
and since 1.11 a sibling module in the same directory is not
included either. Infrahub knows it never scanned those imports,
so with no `watch` key it folds the commit id into the
definition's fingerprint: the definition re-renders or re-runs
on **every commit**, including documentation-only ones. Present
the key — even as `files: []` — and that stops, because the key
is the author's assertion that the list is complete.

That assertion is the reason an inaccurate list is worse than
no list. An incomplete `watch` under-regenerates in silence:
the artifact keeps its old content, the Generator's objects
never appear, and nothing errors anywhere.

`jinja2_transforms` are the exception and should not be flagged
by default. Their closure comes from parsing the template and
following every reference it declares, so a complete Jinja2
closure is trusted on its own. Flag one only where a reference
cannot be followed — a computed `{% include partial_name %}`.

**What does not trigger it.** `watch` governs regeneration
driven by *file* changes inside a proposed change. A proposed
change that only edits node attributes, with no repository
commit, never engages `watch` at all. Do not present a `watch`
finding as a latency win for a workload of that shape; it is
inert there.

## Verify the key against the version under audit

`.infrahub.yml` parsing is `extra="forbid"`, and the failure is
total rather than local: one unsupported key fails the **whole
repository import**, with error-import status and no visible
error in the UI. So before proposing `watch` anywhere, confirm
the version under audit accepts it, and say in the finding how
that was confirmed.

Resolve it from that version's own repository-config model —
not from the published docs, which describe the current
release, and not from recall:

```bash
python -c "from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig as C; print('watch' in C.model_fields)"
```

Read it from the deployed server's image rather than the local
harness where the two can differ: the server parses the
repository config with its own vendored SDK.

The version floors, verified against the 1.11.2 source:

| Section | Accepts `watch` |
| ------- | --------------- |
| `python_transforms` | Yes, from 1.10 |
| `jinja2_transforms` | Yes, from 1.10 |
| `generator_definitions` | Yes, from 1.11 |
| `check_definitions` | **Never** |
| `artifact_definitions` | **Never** |

1.10 accepted the key on Transformations but behaved
differently: it detected a Python transform's whole package
directory and required an empty declaration on Jinja2
transforms. Neither holds from 1.11 on. An audit against 1.10
should report the version, not this rule's fix.

## Checks

For each entry in the three eligible sections:

1. **Key present.** Every `python_transforms` and
   `generator_definitions` entry carries `watch`. Absent means
   re-render-on-every-commit — flag it, including for an entry
   that turns out to need `files: []`.
2. **Shape.** `watch` is a mapping whose only key is `files`,
   holding a list. The bare-list form (`watch: [a, b]`) and any
   other key fail the repository import. A bare `watch:` with
   nothing under it does **not** fail: it parses to null, so it
   counts as no declaration while reading as one. Flag it the
   same as a missing key — it is the harder of the two to see.
3. **Completeness.** Read the entry point. Resolve every import
   to a repository path and confirm the list covers it —
   relative imports of siblings included, since those are not
   detected. Grep for runtime file reads (`open`, `read_text`,
   `yaml.safe_load`, `FileSystemLoader`) and confirm those
   paths are covered too. Third-party and stdlib imports are
   not tracked repository files and must not appear; a
   **generated** `protocols.py` committed in the repo is
   first-party and must.
4. **Resolvability.** Infrahub expands each entry with
   `git ls-files`, so run the same check — it needs no server:

   ```bash
   git ls-files -- transforms/device_config_query.py src/my_package/
   ```

   An entry printing nothing is a typo, a gitignored path, or a
   symlink. It cannot extend the closure, yet still counts as a
   declaration, so it makes the list read as complete while
   contributing nothing.
5. **Ineligible sections.** No `watch` on `check_definitions`
   or `artifact_definitions`. An artifact regenerates as a
   consequence of its transform's closure, so the fix lands on
   the transform entry.
6. **Jinja2, only on an unfollowable reference.** Flag a
   `jinja2_transforms` entry only where a computed include
   leaves the closure incomplete. Walk the include graph to
   decide, and accept **both quote styles** for `include`,
   `import`, `extends`, and `from` — a scan matching only
   single quotes reports a reachable template as an orphan.

## What NOT to flag

- A `python_transforms` or `generator_definitions` entry whose
  `watch.files` is `[]` **and** whose entry point genuinely
  imports nothing first-party and reads no file at runtime.
  That is the correct declaration, not a placeholder.
- A `jinja2_transforms` entry whose includes are all literal
  paths. Its closure is already complete; a `watch` there is
  noise.
- An entry that names a directory rather than the individual
  modules, where the directory is a package consumed as a unit
  (`src/my_package/`). It costs precision, not correctness.
  Note it in the finding body; do not raise a separate finding.
- An audit against a version that does not accept the key on
  the section in question.

## Common Issues

- Seven Python transforms importing the same shared package,
  none declaring `watch` — every commit, documentation
  included, re-fingerprints all seven.
- A `watch` list written against 1.10, when the entry point's
  directory was detected, so it names the shared package but
  omits the sibling query model beside it.
- `watch:` added to an `artifact_definitions` entry, failing
  the whole repository import with no visible error in the UI.
- An entry left in place after the file it names was renamed —
  still counted as a declaration, still contributing nothing.

## How to Fix

Name the entry's real dependencies, derived from the code:

```yaml
python_transforms:
  - name: device_config
    class_name: DeviceConfig
    file_path: transforms/device_config.py
    watch:
      files:
        - transforms/device_config_query.py
        - src/my_package/

  - name: interface_names
    class_name: InterfaceNames
    file_path: transforms/interface_names.py
    watch:
      files: []
```

## Related

- Deriving and reviewing the list:
  [../../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md](../../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md)
  and
  [../../infrahub-managing-generators/rules/registration-watch-dependencies.md](../../infrahub-managing-generators/rules/registration-watch-dependencies.md)
- `.infrahub.yml` reference:
  [../../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
