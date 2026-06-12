---
title: Run Generators End-to-End Before Declaring Done
impact: LOW
tags: testing, integration, infrahubctl, runtime, verification
---

## Run Generators End-to-End Before Declaring Done

Impact: LOW

Unit tests on the input dict do not cover SDK call shape.
Bug classes that pass unit tests but fail at runtime against a
real Infrahub server include:

- HFID encoded as a bare string (treated as ``id``)
- Over-packed HFID list for a single-component target
- List passed to ``RelationshipManager.add`` instead of iterating
- Uniqueness collisions on bootstrap-seeded keys

Every one of these has the same property: the Python code is
syntactically and type-wise fine; only the wire protocol shape is
wrong. **Run the generator against a live test instance before
declaring it done.**

### Concrete workflow

After the generator is implemented and unit-tested:

1. ``infrahubctl generator list`` — confirm the new definition
   registered.
2. ``infrahubctl generator run <name> <target-id>`` — execute
   the generator against a real branch.
3. Verify the created objects exist via the UI or a GraphQL
   query. Confirm relationships resolve.
4. If anything fails, fix and re-run before moving on.

### When this matters most

- Pre-PR self-review on a development branch.
- After any change to relationship reference shape.
- After any schema migration that changes ``human_friendly_id``.

Unit tests are still valuable for ``clean_data()`` helpers, branch
logic, and pure-Python transforms — they just don't replace the
end-to-end run.

Reference: [Infrahub Generator Docs](https://docs.infrahub.app)
