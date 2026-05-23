---
name: infrahub-managing-generators
description: >-
  Creates Infrahub Generators — design-driven automation that builds infrastructure objects from templates and topology definitions.
  TRIGGER when: building design-to-implementation workflows, auto-creating objects from templates, topology-driven generation.
  DO NOT TRIGGER when: designing schemas, writing data transforms, querying live data, populating static data files.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
argument-hint: "[generator-name] [description...]"
metadata:
  version: 1.2.5
  author: OpsMill
---

# Infrahub Generator Creator

## Overview

Expert guidance for creating Infrahub Generators. Generators
query data from Infrahub via GraphQL and create new nodes and
relationships based on the result -- enabling design-driven
automation where a "design" object automatically creates
downstream infrastructure.

## Project Context

Infrahub config:
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

Existing generators:
!`find . -name "*.py" -path "*/generators/*" 2>/dev/null | head -20`

## When to Use

- Building design-driven automation (topology -> devices)
- Creating objects from templates or design definitions
- Implementing idempotent create-or-update workflows
- Auto-generating infrastructure from high-level designs
- Understanding the generator tracking system

## Rule Categories

| Priority   | Category     | Prefix          | Description                       |
| ---------- | ------------ | --------------- | --------------------------------- |
| CRITICAL   | Architecture | `architecture-` | Components, groups                |
| CRITICAL   | Python Class | `python-`       | Generator, generate(), stable it. |
| CRITICAL   | Validation   | `validation-`   | Upstream count checks             |
| CRITICAL\* | Cascade      | `cascade-`      | Multi-layer cascade pattern       |
| HIGH       | Tracking     | `tracking-`     | Upsert, idempotent                |
| HIGH       | API Ref      | `api-`          | Constructor, props                |
| HIGH       | Registration | `registration-` | .infrahub.yml config              |
| MEDIUM     | Patterns     | `patterns-`     | Cleaning, batch, store            |
| LOW        | Testing      | `testing-`      | infrahubctl commands              |

\* `cascade-` rules are CRITICAL **only when building a modular cascade**
(see Step 2 of the workflow). For single-generator solutions, they don't
apply.

## Generator Basics

Every generator has three components:

1. **Target group** -- objects that trigger the generator
2. **GraphQL query** (`.gql` file) -- fetches the design data
3. **Python class** -- inherits from `InfrahubGenerator`,
   implements `generate()`

```python
from infrahub_sdk.generator import InfrahubGenerator

class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        obj = await self.client.create(
            kind="DcimDevice",
            data={"name": "spine-01"},
        )
        await obj.save(allow_upsert=True)
```

## Workflow

Follow these steps when creating a generator:

1. **Identify the design pattern** — What "design"
   object triggers generation? What objects should be
   created from it? Read
   [rules/architecture-components.md](./rules/architecture-components.md)
   for the target group and generator components.
2. **Choose the topology — single generator or cascade?** —
   A *single generator* builds everything from one design
   object in one pass. A *cascade* splits the work across
   multiple generators (one per hierarchy layer), with each
   downstream generator triggered by changes to its
   upstream's output. Use a cascade when:

   - Downstream objects need their own re-run independent of
     the upstream (e.g. IP allocation re-running without
     re-creating devices).
   - Work splits at a hierarchy boundary (topology → devices
     → interfaces).
   - Re-running the upstream is expensive and most runs
     won't change downstream inputs.

   Otherwise, use a single generator. **When ambiguous, ask
   the user** rather than guessing — the cascade pattern
   adds real complexity (schema changes, checksum logic, a
   second generator) and shouldn't be the default. If you
   pick cascade, the
   [rules/cascade-*.md](./rules/cascade-one-layer.md) rules
   apply; if single, they don't.
3. **Write the GraphQL query** — Create a `.gql` file
   that fetches the design data. Read
   [../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)
   for query patterns.
4. **Implement the Python class** — Inherit from
   `InfrahubGenerator`, implement `generate()`. Read
   [rules/python-generate.md](./rules/python-generate.md)
   for the class pattern and
   [rules/api-reference.md](./rules/api-reference.md)
   for available methods.
5. **Validate upstream data before creating** — At the top
   of `generate()`, compare received counts against expected
   counts and raise on mismatch. A partial GraphQL response
   combined with the tracking system silently deletes
   previously-correct downstream objects. See
   [rules/validation-upstream-counts.md](./rules/validation-upstream-counts.md).
6. **Iterate deterministically** — Wrap create-loops in
   `sorted(...)` (or `range(...)`) so re-runs produce stable
   output. See [rules/python-stable-iteration.md](./rules/python-stable-iteration.md).
7. **Make it idempotent** — Use `allow_upsert=True` so
   re-running creates or updates without duplicates.
   See [rules/tracking-idempotent.md](./rules/tracking-idempotent.md).
8. **(Cascade only)** **Guard with a checksum** — Read the
   downstream `checksum.value`, compare against a fresh
   hash of inputs (prefixed by `GENERATOR_VERSION`), and
   skip work when they match. See
   [rules/cascade-checksum-guard.md](./rules/cascade-checksum-guard.md)
   and [rules/cascade-version-constant.md](./rules/cascade-version-constant.md).
9. **Register in .infrahub.yml** — Add under
   `generator_definitions` with the target group. See
   [rules/registration-config.md](./rules/registration-config.md).
10. **Test** — Run `infrahubctl generator` to validate.
    See [rules/testing-commands.md](./rules/testing-commands.md).

## Supporting References

- **[examples.md](./examples.md)** -- Complete Generator
  patterns (POP topology, network segment, minimal,
  modular cascade)
- **[troubleshooting.md](./troubleshooting.md)** -- Reactive
  reference: symptom → first-check table and a
  post-modification verification checklist. Read when a
  cascade isn't settling, or after any cascade change
  before declaring it done.
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching gotchas)
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions Generators work with
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
