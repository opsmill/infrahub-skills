---
title: scope-split-before-data-layer
impact: HIGH
tags: scope, features, split, dependencies, artifacts
---

# Rule: scope-split-before-data-layer

## The rule

After the service questions and before the data
questions, decide whether the request is one feature or
several. Split when any of these holds:

- more than about 10 functional requirements;
- more than about 8 to 10 new node kinds;
- several domains, such as a fiber plant plus DWDM
  channels plus a wavelength service catalog;
- different systems are the source of truth for
  different parts;
- several mechanisms, such as a generator plus imports
  plus checks.

Merge features that share a data dependency or more
than about 30% of their node kinds. Order features by
data dependency, foundation first.

The brief then shows the split in its shape:

1. The `## Features` table has a row per feature, `F1`,
   `F2`, ... in build order. Every feature after F1 has
   a `Depends on` naming earlier IDs only.
2. Every row lists its `Artifacts` from `schema`,
   `objects`, `generator`, `check`, `transform`, `menu`,
   with `schema` first when listed.
3. The `## Data model sketch` has rows for F1 only. Later
   features appear in the Features table and in Open
   items, not in the sketch.

The Features table is present when nothing is split too,
as a single `F1` row, so the next step always reads one
shape.

## Why it matters

A request like "model the whole optical network in one go" yields
a spec too big to review and a model nobody has thought
through past its first domain. The data questions for
later features are worth asking only once F1 is built,
because building F1 changes their answers. Spec-kit
specifies one feature at a time, and its routing runs one
cycle per artifact type in the order the brief lists.

## How to apply

- Recommend the split like any other answer: a question
  block with the proposed features, their order and
  why.
- After the split, ask the data questions for F1 only.
  Give later features an intent, a scope boundary naming
  their node kinds, their artifacts and their open
  items.
- Write one ready-to-paste `/speckit.specify` prompt per
  feature below the table.
- Table format:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema, objects | - | planned | |
| F2 | DWDM channels | Allocate channels without clashes | OpticalChannel, channel pool | schema | F1 | planned | |
| F3 | Wavelength service | One service per customer wavelength | WavelengthService | schema, generator | F2 | planned | |
```

## Incorrect

Every domain sketched in full, and a generator listed
before the schema it reads.

```markdown
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema | - | planned | |
| F2 | Wavelength service | One service per customer wavelength | WavelengthService | generator, schema | | planned | |
```

```markdown
| F2 | WavelengthService | customer + channel | bandwidth (stated) | OpticalChannel (one) | Infrahub | Optical team | answer Q9 |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Sketching every feature | Decisions for later features are made before F1 teaches anything |
| Empty `Depends on` after F1 | The build order is lost |
| `python` or `script` as an artifact | Not a type the specify routing can act on |
