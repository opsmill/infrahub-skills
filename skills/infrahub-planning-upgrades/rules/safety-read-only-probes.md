---
title: safety-read-only-probes
impact: CRITICAL
tags: safety, read-only, upgrade, probes
---

# Rule: safety-read-only-probes

## The rule

The planner writes a plan and nothing else. It never
runs the upgrade, a schema load, or a branch write, and
the plan never gives the upgrade command. It may run,
and show, the read-only probes listed below.

This holds when the user asks you to "just run it".
Deliver the plan, say plainly that you did not upgrade
anything, and point at the upgrade guide for their
deployment.

## Why it matters

An upgrade rewrites the database and cannot be undone
without a restore. Run from the wrong starting version,
it fails or corrupts partway. The exact commands depend
on the deployment (Docker Compose or Helm, Community or
Enterprise, backup tooling), which the planner cannot
see, so a command lifted into the plan is a guess the
user may paste into production.

## How to apply

1. Run or show only these probes:

   | Probe | Where it runs | What it tells you |
   | ----- | ------------- | ----------------- |
   | `infrahubctl info` | anywhere the SDK is installed | the running version and whether the server is reachable |
   | `infrahubctl schema check` | anywhere the SDK is installed | whether schema files validate against the server, without loading them |
   | `infrahubctl branch list` | anywhere the SDK is installed | open branches |
   | `infrahub db showmigrations` | inside the Infrahub server container | current and target database versions |
   | `infrahub upgrade --check` | inside the Infrahub server container | pending migrations, whether the core schema changes, which branches need a rebase; writes nothing |

2. `infrahub upgrade` and `infrahub db` are server
   commands. They run inside the server container,
   wrapped in `docker compose exec` or `kubectl exec`.
   `infrahubctl` has no upgrade command; writing one
   invents a command that looks safe and fails with
   `No such command 'upgrade'`.
3. To see what a hop will do before taking it, run the
   **target** release's `infrahub upgrade --check`
   against the current database. Verified with 1.11.2
   against a 1.10.8 database: it reported the pending
   migrations and wrote nothing.
4. Describe each upgrade step in prose and link the
   upgrade guide for the user's deployment.

## Examples

Compliant: a read-only probe, and the step described
rather than scripted.

```markdown
Check what 1.11 will do to this database; this writes nothing:

    docker compose exec infrahub-server infrahub upgrade --check

Then upgrade the server to 1.11.0 following the upgrade guide for your deployment.
```

Non-compliant: the upgrade itself handed to the user.

```markdown
Run the upgrade:

    docker compose exec infrahub-server infrahub upgrade
```

## Common mistakes

- Running the upgrade because the user asked and the
  containers were up.
- Putting the upgrade command in the plan "for
  convenience".
- A schema load or a branch creation as a "test".
- Hanging `upgrade --check` off `infrahubctl`.
