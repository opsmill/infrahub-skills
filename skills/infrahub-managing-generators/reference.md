# Infrahub Generator Reference

Class signatures, lifecycle, and the tracking
contract that makes generators idempotent. Detailed
rules live in `rules/`; this is the consolidated
quick-reference.

## Contents

- [What a Generator Is](#what-a-generator-is)
- [InfrahubGenerator — Class API](#infrahubgenerator--class-api)
- [Lifecycle: collect_data → generate → tracking cleanup](#lifecycle-collect_data--generate--tracking-cleanup)
- [Object Creation API](#object-creation-api)
- [Idempotency Contract](#idempotency-contract)
- [.infrahub.yml Registration](#infrahubyml-registration)
- [Target Group: CoreGeneratorGroup vs CoreStandardGroup](#target-group-coregeneratorgroup-vs-corestandardgroup)
- [Testing Locally](#testing-locally)

---

## What a Generator Is

A generator turns one "design" object into many
"realised" objects, idempotently. Triggered by
membership in a `CoreGeneratorGroup`, the dispatcher
runs `generate()` for each design, and the tracking
system reconciles created/updated/deleted objects on
every run — so removing a child from the design,
re-running, deletes the corresponding realised
object.

Three pieces:

1. **GraphQL query** (`.gql`) — fetches the design data
2. **Python class** (`InfrahubGenerator` subclass) — implements `generate()`
3. **`.infrahub.yml` entry** under `generator_definitions:`

---

## InfrahubGenerator — Class API

```python
from infrahub_sdk.generator import InfrahubGenerator


class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        ...
```

### Constructor parameters (passed by the dispatcher)

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `query` | `str` | required | GraphQL query name from `.infrahub.yml` |
| `client` | `InfrahubClient` | required | Tracking-enabled SDK client |
| `branch` | `str` | `""` | Branch the run is targeting (auto-detected from git) |
| `root_directory` | `str` | `""` | Repo root path on disk |
| `params` | `dict` | `None` | Query parameters (resolved from `targets`/`parameters`) |
| `convert_query_response` | `bool` | `False` | Populate `self.nodes` with `InfrahubNode` objects |
| `execute_in_proposed_change` | `bool` | `True` | Run inside the proposed-change pipeline |
| `execute_after_merge` | `bool` | `True` | Run again after merge to main |

### Instance properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `self.client` | `InfrahubClient` | **Tracking-enabled** client — use this for all writes |
| `self.nodes` | `list[InfrahubNode]` | Hydrated nodes from the query (only populated when `convert_query_response=True`) |
| `self.related_nodes` | `list[InfrahubNode]` | Nodes related to the target via parent/group |
| `self.store` | `NodeStore` | Nodes indexed by id/hfid |
| `self.branch` | `str` | Branch name |
| `self.root_directory` | `str` | Repo root path |
| `self.logger` | `Logger` | Run logger |
| `self.params` | `dict` | Query parameters bound from `targets`/`parameters` |

### Methods

| Method | Description |
| ------ | ----------- |
| `async generate(data: dict) -> None` | **Implement this.** The only method the dispatcher calls. |
| `async collect_data()` | Runs the registered query. Called automatically by `run()`. |
| `async run(identifier: str, data: dict \| None = None)` | Orchestrates `collect_data()` → `generate()` → tracking cleanup. Don't override. |

---

## Lifecycle: collect_data → generate → tracking cleanup

```text
Dispatcher invokes run() for each target object
  → collect_data() fetches the design via GraphQL
  → tracking context opens (group = generator name + target id)
  → generate(data) runs your code
      → self.client.create/update/save() — each write is tagged
  → tracking context closes
      → objects tagged in this run are kept
      → objects tagged by a prior run that weren't touched are deleted
```

That last step — `delete_unused_nodes=True` is the
default in `run()` — is what makes a generator a
declarative driver of its target state. The catch:
**a buggy generator that creates nothing also
deletes everything from the previous run**. Test
locally before letting it run in the pipeline.

---

## Object Creation API

```python
# Create — with allow_upsert=True for idempotency on re-runs
device = await self.client.create(
    kind="DcimDevice",
    data={
        "name": "spine-01",
        "status": "active",
        "device_type": device_type_id,    # Reference by ID
    },
)
await device.save(allow_upsert=True)

# Fetch existing (read-only — doesn't get tagged for tracking)
existing = await self.client.get(
    kind="LocationBuilding",
    name__value="PAR-1",
)

# Allocate from a resource pool (e.g. IP, prefix)
ip = await self.client.allocate_next_ip_address(
    resource_pool=pool,
    identifier=f"{device_name}-loopback",     # Stable identifier for re-use
)
```

`generate()` must be `async`; every client call
needs `await`. A sync `generate()` silently shadows
the base coroutine and the dispatcher awaits
nothing — no objects get created and no error is
raised. Sync blocking calls (`time.sleep`,
`requests.get`, etc.) inside `generate()` stall the
event loop until a watchdog timeout.

---

## Idempotency Contract

| Knob | Required? | What it does |
| ---- | --------- | ------------ |
| `await obj.save(allow_upsert=True)` | Yes, on every save | Without it, the second run errors out the first time it sees an object that already exists, and the rest of `generate()` never runs. |
| `self.client` (the tagged client) | Yes | Writes via the raw client bypass the tracking group; the cleanup pass can't see those objects on the next run, so they accumulate as orphans. |
| Stable resource identifiers | Strongly recommended | When allocating from pools (IPs, prefixes), pass a stable `identifier=` so re-runs reuse the same allocation instead of grabbing a new one each time. |

Bare client (`self._init_client`) and sync wrappers
are escape hatches that exist for testing — production
generator code uses `self.client` and `await`.

---

## .infrahub.yml Registration

```yaml
queries:
  - name: pop_topology
    file_path: queries/generators/pop_topology.gql

generator_definitions:
  - name: pop_topology
    file_path: generators/pop_topology.py
    class_name: PopTopology
    targets: pop_designs                 # CoreGeneratorGroup name
    query: pop_topology                  # REQUIRED at this level (unlike check_definitions)
    parameters:
      design: name__value
```

Critical shape difference vs `check_definitions`:
**`generator_definitions` requires a top-level
`query:` field.** `check_definitions` rejects one
(see managing-checks). Mixing them up is the #1
registration error.

---

## Target Group: CoreGeneratorGroup vs CoreStandardGroup

The `targets:` group must be a `CoreGeneratorGroup`,
not a `CoreStandardGroup`. The dispatcher only
schedules generators for groups of the
`CoreGeneratorGroup` kind; pointing at a
`CoreStandardGroup` makes the generator load
successfully but never run.

Group membership is set from the **member** side
via `member_of_groups: [...]` — see
[../infrahub-managing-objects/rules/value-relationships.md](../infrahub-managing-objects/rules/value-relationships.md#group-membership-cardinality-many).

---

## Testing Locally

```bash
# Run a generator against a target object
infrahubctl generator pop_topology design=pop-par-01

# Listing generators registered in .infrahub.yml
infrahubctl generator --list
```

Local runs share the tracking group with pipeline
runs, so a successful local run reconciles state the
same way the pipeline would — including the
delete-unused-nodes cleanup. Test on a branch first
unless you're sure the generator won't delete data.

See [rules/testing-commands.md](./rules/testing-commands.md)
for the parameter-binding details and
[rules/tracking-idempotent.md](./rules/tracking-idempotent.md)
for the full tracking contract.

Reference: [Infrahub Generator Docs](https://docs.infrahub.app)
