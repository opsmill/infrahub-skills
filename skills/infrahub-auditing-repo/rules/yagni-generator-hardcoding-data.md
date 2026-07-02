---
title: yagni-generator-hardcoding-data
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, generator, data
---

# Rule: yagni-generator-hardcoding-data

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — Already in this repo (or `opsmill/schema-library`)?

## What It Checks

Generators that hardcode object lists, attribute values, or role
catalogs that should live as YAML data files under `objects/` (or
inherit from a library generic). Generators exist to *compute* objects
from a design definition — when the "design" is a fixed list embedded
in Python, the generator is acting as a misplaced data file.

## Why it matters

Data hardcoded inside a generator is invisible to the rest of the
platform: it doesn't appear in `objects/` diffs, doesn't surface in
data-export tooling, doesn't get touched by the standard object
loaders, and silently divides what the repo presents as "the data"
across both YAML and Python. Reviewers reviewing a roles or sites
change have to know to look in the generator file. Engineers updating
the catalog have to edit Python instead of YAML. Newcomers can't tell
which file is authoritative.

## Checks

1. Generator with a module-level constant list of dicts that map
   1:1 to objects it then creates (`ROLES = [{"name": "spine"}, ...]`).
   The list is data; move it to `objects/roles.yml`.
2. Generator that hardcodes a sequence of `await client.create(...)`
   calls with literal kwargs (no derivation from `data`).
3. Generator that hardcodes peer object lookups by literal name
   (`await client.get(name__value="ROLE_SPINE")`) when the lookup
   target could be an object in `objects/`.
4. Generator that loads a `.json` or `.yaml` file from disk via
   `open()` — the loader is reinventing what `objects/` already
   does, just with a worse path.

## What NOT to flag

- **Bootstrap and seed generators** (typically under `bootstrap/`,
  `seed/`, `demo/`, or named `*_bootstrap.py` / `*_demo_data.py`).
  These exist specifically to seed initial state and are intended to
  hardcode that initial state.
- Generators that hardcode small lookup tables of platform-required
  constants (e.g., RFC 1918 ranges, well-known port numbers,
  protocol IDs) where the values are immutable and externalising
  them would add friction without reducing change frequency.
- Generators whose hardcoded structure encodes algorithm
  configuration rather than data (e.g., a topology generator with
  fixed numeric thresholds for fanout).

## Common Issues

- A generator with `DEVICE_TEMPLATES = [...50 dicts...]` at module
  scope. That's `objects/device-templates.yml` plus a much smaller
  generator that reads them.
- A generator that creates the same five default `Status` objects
  every run via inline literals. Those five objects belong in
  `objects/statuses.yml` and run once via the object loader.
- Two generators with overlapping hardcoded catalogs. Both lose to
  one YAML file plus zero hardcoding in either generator.
