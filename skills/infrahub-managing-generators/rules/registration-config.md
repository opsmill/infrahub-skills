---
title: Generator Registration in .infrahub.yml
impact: HIGH
tags: registration, config, infrahub-yml, targets, parameters, groups, membership
---

## Generator Registration in .infrahub.yml

Impact: HIGH

A generator is registered in `.infrahub.yml` under
`generator_definitions` with its query name, target
group, class name, and the parameter mapping that
turns target attributes into query variables.

### Why it matters

`generator_definitions` carries a top-level `query:`
field — the opposite of `check_definitions`, which
embeds the query under the check itself. Copying the
check shape into a generator block is the most
common setup mistake; Infrahub rejects the config at
load time, so the repository never finishes syncing and
no run is ever enqueued. Read the sync status on the
repository object, or `infrahubctl task list
--include-logs`, to see it. **Not `infrahubctl generator
--list`**: that reads the local `.infrahub.yml` and
never contacts the server, so it lists the malformed
entry happily. `targets:` resolves
strictly against `CoreGeneratorGroup`; pointing it
at a `CoreStandardGroup` of the same name parses
fine but the dispatcher never enqueues runs, so the
generator looks broken with no error message.
Parameter paths like `name__value` are evaluated on
each member of the target group at dispatch time —
a typo here surfaces as the query running with
empty variables and returning zero rows.

### Configuration

```yaml
queries:
  - name: topology_dc
    file_path: queries/topology/dc.gql

generator_definitions:
  - name: create_dc
    file_path: generators/generate_dc.py
    # Must match query name
    query: topology_dc
    # CoreGeneratorGroup name
    targets: topologies_dc
    class_name: DCTopologyGenerator
    parameters:
      # Maps $name to target's name attribute
      name: name__value
```

### Field Reference

| Field        | Required | Description                           |
| ------------ | -------- | ------------------------------------- |
| `name`       | Yes      | Unique Generator identifier           |
| `file_path`  | Yes      | Path to Python file                   |
| `query`      | Yes      | Query name (must match queries entry) |
| `targets`    | Yes      | CoreGeneratorGroup name               |
| `class_name` | Yes      | Python class name                     |
| `parameters` | Yes      | Maps query variables to attributes    |

### Critical Rules

- `query` is matched by exact string against the
  `queries` block; a mismatch (or a missing
  `queries` entry) makes the dispatcher report an
  unknown query and skip the run.
- `targets` resolves only against
  `CoreGeneratorGroup`; pointing it at a different
  group kind parses but never triggers, so the
  generator looks dead with no log line.
- `parameters` maps GraphQL `$variable` names to
  target attribute paths (`name__value`,
  `site__node__name__value`); the path is evaluated
  per group member at dispatch time.

## Populating the Target Group

`targets:` names a group that must **exist and have
members** before the generator dispatches. A group that
exists and is empty produces **no error and no run** —
the pipeline is green and nothing happened. That is the
failure mode to design against, because there is no log
line to find.

### Assign membership from the member side

Group membership is one relationship with two ends,
sharing the identifier `group_member`:

| Declared on | Field | Peer |
| ----------- | ----- | ---- |
| `CoreGroup` | `members` | `CoreNode` |
| every other kind (auto-generated) | `member_of_groups` | `CoreGroup` |

In object data, **write it from the member side**:

```yaml
# WORKS: the peer is CoreGroup, which has a default_filter
- kind: NetTopology
  data:
    - name: dc1-fabric
      member_of_groups:
        - topologies_dc          # resolved by name
```

```yaml
# DOES NOT RESOLVE: the peer is CoreNode
- kind: CoreGeneratorGroup
  data:
    - name: topologies_dc
      members:
        - dc1-fabric             # nothing to match this against
```

The reason is not arbitrary. `CoreGroup.members` peers
**`CoreNode`**, which has no attributes, no
`default_filter` and no `human_friendly_id` — so there
is nothing for a name to resolve against. `CoreGroup`
*does* have `default_filter: name__value`, so the member
side resolves fine.

The general principle, worth carrying beyond groups: **a
relationship whose peer is a bare generic cannot be
resolved by name in object data.** Write from the side
whose peer has a `default_filter` or a
`human_friendly_id`, or supply explicit IDs.

`subscribers` / `subscriber_of_groups` mirror this
exactly on the identifier `group_subscriber`.

### Assert the group resolves and is non-empty

A green pipeline does not mean the generator ran. Two
things commonly leave the group empty on a clean install:

- the data file that creates the group's members is not
  in the loaded set (excluded from `objects:`, or ordered
  after the generator's dispatch)
- membership was written from the group side and silently
  did not resolve

So check it rather than assuming:

```bash
# Does the group exist, and what is in it?
infrahubctl object get CoreGeneratorGroup --branch mybranch

# Is the generator registered, and which group does it target?
infrahubctl generator --list

# Did a run actually happen?
infrahubctl task list --include-logs
```

`infrahubctl generator --list` reads
`generator_definitions` out of `.infrahub.yml` and
prints each name, file, class and target. It never
contacts the server, so it says nothing about whether
the group resolved or a run was enqueued. For that, read
the task list above, or the proposed change's pipeline
output.

In CI, assert non-emptiness explicitly. "The pipeline
passed" and "the generator ran" are different claims.

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md),
[tracking-idempotent.md](tracking-idempotent.md)
