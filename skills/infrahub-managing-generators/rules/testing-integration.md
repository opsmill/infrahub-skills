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

1. ``infrahubctl generator --list`` — confirm the new
   definition registered. ``--list`` is a flag; there is no
   ``generator list`` subcommand, and a bare word there is read
   as the name of a generator to run.
2. ``infrahubctl generator <name> <param>=<target-id> --branch <branch>``
   — execute the generator against a real branch. The name is a
   positional argument, not a ``run`` subcommand. ``--branch`` is
   not optional here: a generator run writes, and a write with no
   branch lands on ``main``, which
   ``skills/infrahub-common/rules/workflow-branch-for-crud.md``
   rates CRITICAL.

   Everything after the name is a query variable in ``key=value``
   form: the target is passed as a variable the generator's
   ``.gql`` declares, never as a bare id. A token with no ``=`` is
   dropped silently, and the run does **not** then fail on a
   missing variable — with no variables left, ``infrahubctl
   generator`` falls back to running the generator over every
   member of the definition's target group. A mistyped target is a
   mass write, not a no-op. Verified against SDK 1.23.1
   (``ctl/utils.py`` ``parse_cli_vars``, ``ctl/generator.py``).
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
