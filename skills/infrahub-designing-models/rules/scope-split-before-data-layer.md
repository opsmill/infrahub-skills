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
   `F2`, ... in build order. Each row's `Depends on`
   names the earlier features it needs, or `-` when it
   needs none, and never a later or unknown ID. Its
   `Handoff` is a self-contained description that can
   enter any downstream workflow.
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
because building F1 changes their answers. A portable
handoff for each feature lets the user preserve that
order in whichever specification, planning, ticketing or
implementation workflow they already use.

## How to apply

- Recommend the split like any other answer: a question
  block with the proposed features, their order and
  why.
- After the split, ask the data questions for F1 only.
  Give later features an intent, a scope boundary naming
  their node kinds, their artifacts and their open
  items.
- Write one self-contained `Handoff` per feature. State
  the outcome, scope, artifacts and dependencies without
  assuming a particular command or workflow framework.
- Table format:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Handoff |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema, objects | - | planned | Design and implement the fiber plant model sketched below, then populate its initial objects. |
| F2 | DWDM channels | Allocate channels without clashes | OpticalChannel, channel pool | schema | F1 | planned | After F1, design the channel model and allocation pool using the decisions and open items in this brief. |
| F3 | Wavelength service | One service per customer wavelength | WavelengthService | schema, generator | F2 | planned | After F2, design the service model and automate service creation from the channel pool. |
```

## Incorrect

Every domain sketched in full, and a generator listed
before the schema it reads.

```markdown
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Handoff |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema | - | planned | |
| F2 | Wavelength service | One service per customer wavelength | WavelengthService | generator, schema | | planned | Run the framework's specify command for this feature. |
```

```markdown
| F2 | WavelengthService | customer + channel | bandwidth (stated) | OpticalChannel (one) | Infrahub | Optical team | answer Q9 |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Sketching every feature | Decisions for later features are made before F1 teaches anything |
| Empty `Depends on` | Reads as missing, not as "no prerequisite"; write `-` |
| `python` or `script` as an artifact | Not an artifact type an Infrahub implementation skill produces |
| Framework command as the handoff | Couples the brief to one workflow instead of describing the work |
