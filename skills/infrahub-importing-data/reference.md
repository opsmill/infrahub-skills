# CSV Import Reference

Mapping tables and decision matrices used by the
skill. Most details are spelled out in individual
rule files; this page collects the parts you reach
for repeatedly during a single import session.

## Heuristic order: column → attribute

Apply in this order. Stop at the first match.

| Order | Heuristic | Example | Notes |
| ----- | --------- | ------- | ----- |
| 1 | Exact match (case-sensitive) | `name` → `name` | Cheapest; trust it without confirming |
| 2 | snake_case round-trip | `Serial Number` → `serial_number` | Handles spreadsheet capitalization |
| 3 | Display-label fuzzy | `Rack U Position` ↔ `rack_u_position` (label `"Rack U Position"`) | Read the schema's `label` and compare case-insensitive |
| 4 | Unit-strip | `Memory (GB)` → `memory` | Strip parenthesized units before re-matching steps 1–3 |
| 5 | Unmapped → interview | `gpu_count` (no attribute) | Defer to the user; never invent a binding |

Anything past step 4 is a candidate for the
fail-closed gate (see
[rules/workflow-fail-closed-on-unmapped-columns.md](./rules/workflow-fail-closed-on-unmapped-columns.md)).

## File envelope (reminder)

Every emitted file conforms to the managing-objects
envelope. The full rule is at
[../infrahub-managing-objects/rules/format-structure.md](../infrahub-managing-objects/rules/format-structure.md).

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: <NodeKind>       # full kind, e.g. OrganizationManufacturer
  data:
    - <attribute>: <value>
```

`apiVersion`, `kind: Object`, `spec.kind`, and
`spec.data` are always required.

## HFID length → reference shape

When emitting a relationship reference, the shape
follows the target node's `human_friendly_id`. Full
rule and rationale: [../infrahub-managing-objects/rules/value-relationships.md](../infrahub-managing-objects/rules/value-relationships.md).

| Target HFID | Reference shape | Example |
| ----------- | --------------- | ------- |
| `[name__value]` | scalar string | `manufacturer: Dell` |
| `[parent__shortname__value, name__value]` | YAML list of length 2, in declared order | `rack: ["lab-1", "Rack-A"]` |
| `[a__value, b__value, c__value]` | YAML list of length 3 | `peer: ["x", "y", "z"]` |

Never invent the HFID order. Read it from the
target node's schema and emit the list in exactly
that order — swapping two elements still parses but
resolves to the wrong row.

## File naming for emitted output

Use numeric prefixes so the loader sees dependencies
in order. Full rule:
[../infrahub-managing-objects/rules/organization-load-order.md](../infrahub-managing-objects/rules/organization-load-order.md).

Pattern: `NN_<kind-lowercased-plural>.yml`

```text
output_dir/
  01_manufacturers.yml      # no dependencies
  02_locations.yml          # no dependencies
  03_device_types.yml       # depends on 01
  04_devices.yml            # depends on 02 + 03
```

When two kinds share a prefix because they depend
on the same earlier file but not on each other, use
a letter suffix: `03_device_types.yml`,
`03a_module_types.yml`.

## Branch name pattern

Default: `csv-import-YYYYMMDD-HHMM`. The timestamp
form is collision-free across re-runs. The user can
override in the interview.

```bash
infrahubctl branch create csv-import-20260621-1430
infrahubctl object validate ./output_dir/ --branch csv-import-20260621-1430
infrahubctl object load    ./output_dir/ --branch csv-import-20260621-1430
```

## Interview question template

When the up-front interview is needed (see
[rules/workflow-up-front-interview.md](./rules/workflow-up-front-interview.md)),
batch every ambiguity into a single multi-choice
round. Suggested shape:

```text
I need a few decisions before writing any files.

1. The column "Status" has values ["Active",
   "Maint"]. The DcimDevice.status dropdown has
   choices {active, maintenance, retired}. Map:
   a) Active → active, Maint → maintenance
   b) Active → active, Maint → ??? (you tell me)
   c) Skip this column

2. Rows in inventory.csv repeat per interface, so
   `device.name` is constant within groups of rows.
   Treat as:
   a) Single DcimDevice with inline component
      children (interfaces under each device)
   b) Two separate files: 03_devices.yml +
      04_interfaces.yml with references

3. Branch name (default: csv-import-20260621-1430):
   a) Use default
   b) Use a custom name (which one?)

4. Stamp every value with a lineage tag?
   a) No
   b) Yes, source=<some Account or Repository name>
```

Stream-of-consciousness questions during emission
are worse than this batched form — they break the
deterministic re-run loop and make it harder for the
user to review the plan before any file is written.

## Decision: component children vs split kinds

When the parent rows repeat in the CSV (each row is
really a child plus its parent's columns), you have
two valid emissions:

| Option | When it's right | Output shape |
| ------ | --------------- | ------------ |
| Inline component children | The child has no meaning outside the parent (e.g., interfaces of a device); the schema declares Component/Parent with matching identifiers | One file per parent kind; children nested under the relationship name with `kind:` + `data:` |
| Split into separate kinds | The child is independently queryable / referenced by other kinds, or its lifecycle is decoupled | Two numbered files (e.g., `03_devices.yml`, `04_interfaces.yml`) with HFID-shape references between them |

Always confirm the choice in the interview — the
right call is user-specific.
