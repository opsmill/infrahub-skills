---
title: practices-transform-watch-dependencies
impact: MEDIUM
tags: audit, practices, transforms, watch, artifacts, regeneration
---

# Rule: practices-transform-watch-dependencies

**Severity**: MEDIUM
**Category**: Best Practices

## What It Checks

`python_transforms` and `jinja2_transforms` entries in `.infrahub.yml`
whose real file dependencies cannot be auto-detected, yet which declare
no `watch:` key. Two signals:

1. A `jinja2_transforms` template that pulls in another template through
   a runtime variable (`{% include some_var %}`, `{% import x %}`,
   `{% extends layout %}`) rather than a literal string path.
2. A `python_transforms` file that imports a helper from a sibling
   top-level package (for example `from shared.formatting import ...`,
   `from utils import ...`) that lives outside the transform's own
   directory.

Only `python_transforms` and `jinja2_transforms` accept `watch`.
`artifact_definitions` and `generator_definitions` do NOT — their config
models forbid unknown keys, so adding `watch:` there makes `.infrahub.yml`
fail to import. An artifact regenerates as a consequence of its
transform's dependency closure, so the fix always lands on the transform
entry, never on the artifact. (Generator-side `watch` support is on the
roadmap but not yet released — do not suggest it today.)

## Why it matters

Infrahub regenerates an artifact only when a changed file is inside its
Transformation's dependency closure. Auto-detection follows a Jinja2
template's static includes and a Python transform's own package
directory — but it cannot follow a dynamic `{% include a_variable %}`
or a helper imported from another top-level package. When a reference
cannot be resolved, the closure is marked incomplete and Infrahub falls
back to regenerating that transform's artifacts on *any* file change in
the repository. On a large repo this turns an unrelated one-line commit
into a full artifact rebuild across every device the transform targets —
the precise scaling cost the closure gate is meant to avoid. Declaring
the real dependencies with `watch.files` both adds them to the closure
and marks it complete, restoring targeted regeneration. Left undeclared,
the symptom is silent: the pipeline still produces correct artifacts, it
just does far more work than it should, and the cost only surfaces as
proposed-change latency under scale.

## Checks

For each `jinja2_transforms` and `python_transforms` entry in
`.infrahub.yml`:

1. **Jinja2 dynamic includes**: open the `template_path` (and templates
   it statically pulls in). If any `{% include %}`, `{% import %}`, or
   `{% extends %}` names a variable rather than a string literal, the
   closure is incomplete. If the entry has no `watch.files` covering the
   directory those partials live in, emit a finding.
2. **Python cross-package imports**: open the `file_path`. If it imports
   from a module that resolves outside the transform's own directory
   (a sibling top-level package such as `shared/` or `utils/`), and the
   entry has no `watch.files` covering that path, emit a finding.
3. **Never suggest `watch` on `artifact_definitions` or
   `generator_definitions`** — those models reject the key, and the
   generator-side feature is not yet released.

## What NOT to flag

- Transforms whose includes are all literal string paths and whose
  imports stay inside their own package — auto-detection already covers
  them, so `watch` would be redundant noise.
- Transforms that already declare a `watch.files` entry covering the
  undetectable dependency.
- Standalone Python transforms with no external imports (self-contained
  single file).
- `check_definitions`, `artifact_definitions`, and
  `generator_definitions` — they have no closure/`watch` concept, so a
  change touching their code is handled differently.

## Common Issues

- A Jinja2 template with `{% include partial_name %}` (variable) and no
  `watch` — every repo commit rebuilds its artifacts.
- A Python transform `from shared.formatting import render` where
  `shared/` is a top-level sibling of `transforms/`, with no `watch`
  entry, so edits to `shared/formatting.py` never targeted-regenerate
  (they only regenerate via the any-change fallback).
- `watch:` mistakenly added to an `artifact_definitions` entry — the
  repository import fails with an "extra fields not permitted" error.

## How to Fix

Add a `watch.files` list to the transform entry, naming the directory
(recursive) or the individual files it depends on. Listing the directory
is usually simplest and also marks the closure complete.

Jinja2 transform that dynamically includes partials:

```yaml
jinja2_transforms:
  - name: device_config
    query: device_config_query
    template_path: templates/device_config.j2
    watch:
      files:
        - templates/partials/
```

Python transform importing shared helpers:

```yaml
python_transforms:
  - name: device_name_attribute
    class_name: DeviceNameAttribute
    file_path: transforms/device_name_attribute.py
    watch:
      files:
        - shared/helpers.py
        - utils/
```

## Related

- `.infrahub.yml` reference:
  [../../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
- Transform artifact regeneration behaviour:
  [../../infrahub-managing-transforms/rules/artifacts-async-regen-polling.md](../../infrahub-managing-transforms/rules/artifacts-async-regen-polling.md)
