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
without a restore. Run from more than one minor
version back, it is outside what Infrahub supports, and
nothing in the upgrade stops you. The exact commands depend
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
   | `infrahub db showmigrations` | inside an Infrahub server container; **from 1.10.0** | current and target database versions, and each migration |
   | `infrahub upgrade --check` | inside an Infrahub server container | from 1.10.0: each pending migration, whether the core schema changes, which branches need a rebase. Before 1.10.0: one line with the graph-version gap and the pending count. Writes nothing either way |

   `infrahub db showmigrations` does not exist before
   1.10.0; naming it for an older hop invents a command.
2. `infrahub upgrade --check` and
   `infrahub db showmigrations` are server commands.
   They run inside an Infrahub server container.
   `infrahubctl` has no upgrade command; writing one
   invents a command that looks safe and fails with
   `No such command 'upgrade'`.
3. To see what a hop will do before taking it, run the
   **target** release's `infrahub upgrade --check`
   against the current database, in a one-off container
   from the target image. `docker compose exec` into the
   running server uses the release that is running now,
   which sees its own graph version and reports nothing
   pending. On Docker Compose, where the image tag is
   `${VERSION}`:

   ```bash
   VERSION=1.11.0 docker compose run --rm --no-deps infrahub-server infrahub upgrade --check
   ```

   On Kubernetes, run the same command in a one-off pod
   from the target image with the server's
   configuration. Verified on Docker Compose against a
   1.10.8 database, with 1.11.0 and with 1.11.2: each
   reported what the hop would do and wrote nothing.
4. Describe each upgrade step in prose and link the
   upgrade guide for the user's deployment.
5. In prose, write "the upgrade", never the command,
   even to say you did not run it. The only form of the
   upgrade command a plan contains is the
   `infrahub upgrade --check` probe. A reader skimming
   for commands copies whatever is backticked, and
   "I did not run `infrahub upgrade`" hands it over all
   the same.

## Examples

Compliant: a read-only probe, and the step described
rather than scripted.

```markdown
Check what 1.11 will do to this database; this runs the 1.11.0 image once and writes nothing:

    VERSION=1.11.0 docker compose run --rm --no-deps infrahub-server infrahub upgrade --check

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
- Naming the upgrade command in prose to say it was
  not run, instead of writing "the upgrade".
- A schema load or a branch creation as a "test".
- Hanging `upgrade --check` off `infrahubctl`.
