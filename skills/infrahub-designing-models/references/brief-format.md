# Design Brief Format

The single home for the brief's location, sections and
tables. The rules link here; none of them restate it.

## Location

One brief per design, at
`docs/designs/<design-slug>/design-brief.md`, even when
the repository keeps other design documents elsewhere.
The handoffs and the Next steps name this path.

`<design-slug>` is two to four lowercase words joined by
hyphens, such as `oob-network`. Extending a design
edits its existing brief; it never starts a second one.

## Sections

These `##` headings, spelled and ordered exactly like this:

1. `## Summary`: the problem, the intended outcome, and
   what is not decided yet. Three to five sentences.
2. `## Inputs`: the files the user provided, as a table,
   or the word `none`.
3. `## Business`: the `Value:` line, then who uses the
   data and what is out of scope.
4. `## Service`: what a customer or internal team
   orders, what the requester decides compared with
   what the network team derives, and the lifecycle
   states with who moves each one.
5. `## Reference design`: the closest OpsMill reference
   design and what this design follows from it.
6. `## Features`: always present, one row per feature,
   then the plan map.
7. `## Data model sketch`: the node kinds of F1, then
   the model map.
8. `## Mechanisms`: a table of each behavior, the
   mechanism that delivers it, and why.
9. `## Decision log`: every decision and its provenance.
10. `## Open items`: what is not known, and who owes it.
11. `## Next steps`: what the reader does next, in
    order.

## Reference design

```markdown
Closest: infrahub-demo-sp
Reused: the service-with-sites pattern (L3Vpn and L3VpnSite)
Different: route distinguishers come from a pool, not from the order
Marketplace: infrahub/base-schemas (Site and Device for the VPN's sites)
```

`Closest:` names a design from
[reference-designs.md](reference-designs.md), the full
`https://github.com/opsmill/...` URL of a newer demo or
solution you read, or `none` with the reason.
`Reused:` is required whenever a design is named.
`Marketplace:` names each published schema or
collection the design builds on, with the node kinds it
covers; or `none matched` with the reason; or
`not searched` with the reason, also kept as an open
item.

## Value line

The first line of `## Business`:

```markdown
Value: Lower change failure costs (recommended: duplicate rd values in vpn-customers.xlsx); Reduced engineering effort (stated: answer Q1)
```

The drivers from
[../rules/brief-value-drivers.md](../rules/brief-value-drivers.md),
spelled as listed there, in rank order, separated by
`;`. Each is tagged `stated` or `recommended` in
parentheses, followed by what it rests on. A value no
driver fits is written in the user's words as
`Other: audit evidence for every change (stated: answer Q1)`; it is
always `stated`, and a feature names it as `Other`. A figure
appears only on a `stated` entry, with its source:
`answer Q<n>`, `request`, or `<input file>:<locator>`.

## Inputs table

```markdown
| File | Taken from it |
| --- | --- |
| sites.xlsx | site_code identifies each site; country becomes the parent |
| oob-diagram.drawio | Two console servers per site and the devices cabled to each port |
```

One row per file, named as the user named it, including
files pasted into the conversation.

## Features table

```markdown
| ID | Feature | Intent | Value | Scope boundary | Artifacts | Depends on | Status | Handoff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Reduced engineering effort | Site, FiberCable, Strand | schema, objects, generator | - | planned | Design and implement the fiber plant model, then populate its initial objects, as designed in F1 of docs/designs/metro-optical/design-brief.md. |
| F2 | DWDM channels | Allocate channels without clashes | Lower change failure costs | OpticalChannel, channel pool | schema | F1 | planned | After F1, design the channel model and allocation pool, as designed in F2 of docs/designs/metro-optical/design-brief.md. |
```

- `ID` is `F1`, `F2`, ... in build order. An ID never
  changes once a spec refers to it.
- `Value` names the drivers the feature serves, from the
  `Value:` line, and no figures. F1's names the first
  driver on that line.
- `Artifacts` is an ordered, comma-separated list from
  exactly these values: `schema`, `objects`, `generator`,
  `check`, `transform`, `menu`. `schema` comes first
  whenever it is listed, because everything else reads
  it.
- Each artifact is built by one skill:

  | Artifact | Skill |
  | -------- | ----- |
  | `schema` | `infrahub-managing-schemas` |
  | `objects` | `infrahub-managing-objects`, or `infrahub-importing-data` when the objects come from CSV or TSV files listed in Inputs |
  | `generator` | `infrahub-managing-generators` |
  | `check` | `infrahub-managing-checks` |
  | `transform` | `infrahub-managing-transforms` |
  | `menu` | `infrahub-managing-menus` |

- Data the user only described, such as a spreadsheet,
  a wiki page or another system nobody provided, goes to
  `infrahub-managing-objects`. Name `infrahub-importing-data`
  only for CSV or TSV files the brief lists in Inputs.
- `Depends on` names the earlier features a feature
  needs, or `-` when it needs none. It is never empty,
  and never names a later or unknown ID. A later
  feature can be independent; write `-` rather than a
  dependency it does not have.
- `Status` is `planned`, `specified` once a spec or
  plan exists for the feature, or `built` once its
  artifacts are loaded. It starts as `planned`.
- `Handoff` states the outcome, scope, artifacts and
  dependencies, and names the brief's path and the
  feature ID, so the downstream workflow reads the
  details from the brief. It does not name a framework
  command. The user can paste it into their existing
  specification, planning, ticketing or implementation
  workflow, together with the brief it names.

### Plan map

A Mermaid graph inside the brief's `## Features`
section, right after the table, with no heading of its
own. A reader sees the build order at a glance. It is
drawn from the table, and the table stays the source:
change the table first, then redraw the map.

- One node per feature, labelled with its ID, its name
  and its artifacts.
- One arrow from each feature in `Depends on` to the
  feature that depends on it. A feature with `-` has no
  incoming arrow.
- Break a label over two lines inside the quotes, never
  with `<br>`.

```mermaid
graph LR
  F1["F1 Fiber plant
  schema, objects, generator"]
  F2["F2 DWDM channels
  schema"]
  F1 --> F2
```

## Data model sketch table

```markdown
| Feature | Node kind | Identified by | Key attributes (value class) | Peers (cardinality) | Source of truth | Owner | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | LocationSite | site_code | name, country (imported) | ConsoleServer (many) | Sites sheet | Facilities team | sites.xlsx:site_code |
| F1 | FiberCable | cable ID | length (stated) | Strand (many) | Infrahub | open: O1 | answer Q5 |
```

- Value classes: `stated` (the requester gives it),
  `pool` (allocated from a resource pool), `computed`
  (derived from other values), `imported` (read from
  another system).
- `Source of truth` is the system that is authoritative
  for the node kind. `Evidence` is where you learned the
  row's facts: `file:column`, `file:element`,
  `answer Q<n>`, `request` (the user's opening message),
  or the reference design's name.
- `Peers` names each peer node kind spelled exactly as
  its `Node kind`, followed by the cardinality:
  `Strand (many)`. A peer this design does not define,
  because it exists elsewhere or nobody described it,
  gets no sketch row: name it in `Peers` and track what
  is unknown about it in Open items.
- A value nobody knows is written `open: O<n>`, pointing
  at a real entry in Open items.

### Model map

A Mermaid graph inside the brief's `## Data model
sketch` section, right after the table, with no heading
of its own. Like the plan map, it is drawn from the
table and the table stays the source.

- One node per node kind in the sketch, labelled with
  the node kind.
- One line between a node kind and each peer in its
  `Peers` cell. Direction does not matter; a line the
  table does not have is a mistake.

```mermaid
graph LR
  LocationSite --- ConsoleServer
  FiberCable ---|many| Strand
```

## Decision log table

```markdown
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Console ports are identified by server and port number | stated | |
| 2 | Channel numbers come from a number pool | recommended | Pool avoids clashes; you allocate by hand today (strong) |
| 3 | Who approves new OOB sites | open | O2 |
| 4 | Direction A (follow infrahub-demo-otn), with B2 (strands as their own node kind); not taken: B (a custom model) | stated | |
```

- The design direction is one row whose Decision cell
  starts `Direction <letter>`, then names the IDs
  borrowed from other directions and, after `not
  taken:`, the directions not chosen. Its tag follows
  [../rules/interview-design-directions.md](../rules/interview-design-directions.md).
- `Basis` on a `recommended` row is the reason you
  recommended it. On an `open` row it is the open item
  that tracks the question, `O<n>`, which must be a real
  entry in Open items.

## Mechanisms table

```markdown
| Feature | Behavior | Mechanism | Driven by | Produces | Runs when | Why |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | A new cable gets its strands | generator | FiberCable | Strand per fiber | a cable is added | creates other nodes from a design |
| F1 | No two cables share a cable ID | schema constraint | FiberCable | uniqueness on cable ID | every change | the schema enforces it without code |
| F2 | Channel numbers per span | resource pool | FiberCable | a channel number | a channel is requested | no hand allocation |
```

- `Mechanism` is one of `generator`, `check`,
  `transform`, `computed attribute`, `resource pool`,
  `schema constraint`.
- Every `generator`, `check` or `transform` a feature
  lists in `Artifacts` has a row here, and every such row
  belongs to a feature that lists it.
- `Driven by` names the node kind that triggers or feeds
  the behavior, from the sketch for F1. `Produces` says
  what it creates, enforces or renders. `Runs when`
  says what starts it: a change, or a schedule the user
  stated ("every night"); what runs a schedule is a
  question for the building skill or an open item.
- Prefer a `schema constraint` to a `check` for a rule
  the schema can enforce, such as uniqueness.

## Open items

```markdown
- O1: Who owns cable records? (owner: unknown, field operations or planning team; affects F1)
- O2: Who approves new OOB sites? (owner: network operations; affects F1, F2)
```

Each item names the features its answer changes
(`affects F1, F2`), including every feature with a cell
that refers to it.

## Next steps

```markdown
1. Settle O1 with field operations.
2. Build F1 Fiber plant: run the Schema Manager, then the Object Manager and the Generator Manager.
3. When F1 is loaded, build F2 DWDM channels with the Schema Manager.
```

- One numbered step per feature, after the features it
  depends on. Open items that F1's sketch waits on come
  first, one step per owner.
- Name skills as the mapping above does
  (`infrahub-managing-schemas`), optionally with their
  short name (Schema Manager).
- Word each feature's step for the workflow the
  repository already uses, without asking: with
  `.specify/`, give its Handoff to `/speckit.specify`;
  with another specification or planning setup the user
  named, take the Handoff there; with none, name the
  skill for each
  artifact, in the order of the `Artifacts` cell, using
  the mapping above.
