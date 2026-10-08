# Design Brief Format

The single home for the brief's location, sections and
tables. The rules link here; none of them restate it.

## Location

One brief per design, named `design-brief.md`:

| Repository | Path |
| ---------- | ---- |
| Uses spec-kit (`.specify/` exists) | `specs/<design-slug>/design-brief.md` |
| Does not | `docs/designs/<design-slug>/design-brief.md` |

`<design-slug>` is two to four lowercase words joined by
hyphens, such as `oob-network`. Extending a design
edits its existing brief; it never starts a second one.

## Sections

These `##` headings, spelled and ordered exactly like this:

1. `## Summary`: the problem, the intended outcome, and
   what is not decided yet. Three to five sentences.
2. `## Inputs`: the files the user provided, as a table,
   or the word `none`.
3. `## Business`: who uses the data, the incident it
   prevents, and what is out of scope.
4. `## Service`: what a customer or internal team
   orders, what the requester decides compared with
   what the network team derives, and the lifecycle
   states with who moves each one.
5. `## Features`: always present, one row per feature.
6. `## Data model sketch`: the node kinds of F1.
7. `## Mechanisms`: for each behavior, a computed
   attribute, a resource pool, a check, a transform or
   a generator, and why.
8. `## Decision log`: every decision and its provenance.
9. `## Open items`: what is not known, and who owes it.

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
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema, objects | - | planned | |
| F2 | DWDM channels | Allocate channels without clashes | OpticalChannel, channel pool | schema | F1 | planned | |
```

- `ID` is `F1`, `F2`, ... in build order. An ID never
  changes once a spec refers to it.
- `Artifacts` is an ordered, comma-separated list from
  exactly these values: `schema`, `objects`, `generator`,
  `check`, `transform`, `menu`. `schema` comes first
  whenever it is listed, because everything else reads
  it.
- `Depends on` names the earlier features a feature
  needs, or `-` when it needs none. It is never empty,
  and never names a later or unknown ID. A later
  feature can be independent; write `-` rather than a
  dependency it does not have.
- `Status` starts as `planned`. `Spec` stays empty until
  a spec exists.

Below the table, give each feature a ready-to-paste
prompt:

```markdown
F1 prompt: `/speckit.specify Fiber plant: sites, cables and strands, as sketched in F1 of docs/designs/metro-optical/design-brief.md`
```

## Data model sketch table

```markdown
| Feature | Node kind | Identified by | Key attributes (value class) | Peers (cardinality) | Source of truth | Owner | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | LocationSite | site_code | name, country (imported) | ConsoleServer (many) | Sites sheet | Facilities team | sites.xlsx:site_code |
| F1 | OpticalChannel | channel number | frequency (pool) | Strand (two) | Infrahub | open: O1 | answer Q5 |
```

- Value classes: `stated` (the requester gives it),
  `pool` (allocated from a resource pool), `computed`
  (derived from other values), `imported` (read from
  another system).
- `Source of truth` is the system that is authoritative
  for the node kind. `Evidence` is where you learned the
  row's facts: `file:column`, `file:element`, or
  `answer Q<n>`.
- A value nobody knows is written `open: O<n>`, pointing
  at a real entry in Open items.

## Decision log table

```markdown
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Console ports are identified by server and port number | stated | |
| 2 | Channel numbers come from a number pool | recommended | Pool avoids clashes; you allocate by hand today (strong) |
| 3 | Who approves new OOB sites | open | |
```

## Open items

```markdown
- O1: Who owns the channel plan? (owner: unknown, optical or planning team)
```
