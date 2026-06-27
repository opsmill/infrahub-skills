---
title: yagni-python-transform-that-could-be-jinja2
impact: MEDIUM
ladder_step: 5
tags: audit, yagni, transform, jinja2
---

# Rule: yagni-python-transform-that-could-be-jinja2

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 5 — Can a Jinja2 transform produce it?

## What It Checks

Python transforms whose output is string formatting — concatenation,
substitution, conditional sections — with no real computation. A
Jinja2 template expresses the same output in fewer lines, without
Python runtime overhead, and renders directly in the Infrahub UI
preview.

## Why it matters

When the transform body is `f"interface {name}\n  description {desc}\n  ip {ip}"`,
the cost of the Python form is everything around the string: an
`InfrahubTransform` subclass, an async function, error handling for
nothing, plus a registration entry under `python_transforms` instead
of `jinja2_transforms`. The Jinja2 form is one `.j2` file. Reviewers
read it in two seconds. Operators can preview it from the proposed-
change UI without running Python.

## Checks

1. Transform whose `transform` method only returns an f-string or
   string concatenation built from query results.
2. Transform using `"\n".join([...])` to build line-oriented output
   (interface configs, BGP stanzas, ACL entries).
3. Transform whose only conditionals are
   `if x: out += "..."; else: out += "..."`. Jinja2 `{% if %}` does
   this natively.
4. Transform that imports no libraries beyond
   `from infrahub_sdk.transforms import InfrahubTransform` and uses no
   Python features beyond loops, conditionals, and string formatting.

## What NOT to flag

- Transforms parsing or computing — IP arithmetic, subnet math,
  hashing, base64, JSON re-shaping with non-trivial structure.
- Transforms calling external libraries or services.
- Transforms with stateful logic between iterations (running totals,
  ordering by computed value, deduplication that requires sets).
- Hybrid transforms (Python pre-processing + Jinja2 rendering) where
  the Python step does real work.

## Common Issues

- A 40-line Python transform whose output a 12-line `.j2` file would
  produce. Move it to `jinja2_transforms` in `.infrahub.yml` and
  delete the Python file.
- Half a Python transform that already calls `jinja2.Template(...)`
  inline. The intent is already Jinja2 — promote it to a real
  template file.
- Identical Python transforms differing only in the template string.
  Consolidate into one Jinja2 template and parameterize via the
  query.
