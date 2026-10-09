---
title: scope-split-before-data-layer
impact: HIGH
tags: scope, features, split, dependencies, artifacts
---

# Rule: scope-split-before-data-layer

## The rule

After the service questions and before the data
questions, decide whether the request is one feature or
several. Consider a split when any of these holds:

- more than about 10 functional requirements;
- more than about 8 to 10 new node kinds;
- several domains, such as a fiber plant plus DWDM
  channels plus a wavelength service catalog;
- different systems are the source of truth for parts
  that serve different business outcomes (importing
  reference data, such as sites from a facilities
  sheet, is not one of them);
- several mechanisms, such as a generator plus imports
  plus checks.

These signals only propose a split. Whatever the
signal, keep a split only if every feature, F1 included,
delivers part of the business outcome on its own. A
split by mechanism passes that test when, for example,
F1 delivers the inventory and F2 the automation built on
it. A foundation such as locations or a hierarchy does
not pass it: it is not a feature by itself and goes into
the first feature that needs it.

Merge two candidate features only when they cannot be
built apart, because each needs the other's node kinds,
or when more than about 30% of the node kinds they
define are the same. A feature that adds a generator, a
check or a transform to an earlier feature's node kinds
defines none of them, so it is not merged for that. Depending on the same earlier feature is not a
reason to merge: F3 and F4 can both depend on F2 and
stay separate. Order features by data dependency: a
feature comes after every feature it depends on.

The brief then shows the split in its shape:

1. The `## Features` table has a row per feature, `F1`,
   `F2`, ... in build order. Each row's `Depends on`
   names the earlier features it needs, or `-` when it
   needs none, and never a later or unknown ID. Its
   `Handoff` names the brief and the feature ID and
   can enter any downstream workflow.
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
because building F1 changes their answers. A handoff for
each feature, naming the brief it comes from, lets the
user preserve that order in whichever specification, planning, ticketing or
implementation workflow they already use.

## How to apply

- Before recommending a split, write each feature's
  intent as the part of the business problem it solves.
  A feature whose intent is only "so a later feature can
  use it" is a foundation; fold it into that feature.
- Recommend the split like any other answer: a question
  block with the proposed features, their order and
  why.
- After the split, ask the data questions for F1 only.
  Give later features an intent, a scope boundary naming
  their node kinds, their artifacts and their open
  items.
- Write one `Handoff` per feature. State the outcome,
  scope, artifacts and dependencies, and name the
  brief's path and the feature ID, without assuming a
  particular command or workflow framework.
- Table format:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Handoff |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Fiber plant | Know which strand runs where | Site, FiberCable, Strand | schema, objects | - | planned | Design and implement the fiber plant model, then populate its initial objects, as designed in F1 of docs/designs/metro-optical/design-brief.md. |
| F2 | DWDM channels | Allocate channels without clashes | OpticalChannel, channel pool | schema | F1 | planned | After F1, design the channel model and allocation pool, as designed in F2 of docs/designs/metro-optical/design-brief.md. |
| F3 | Wavelength service | One service per customer wavelength | WavelengthService | schema, generator | F2 | planned | After F2, design the service model and automate service creation from the channel pool, as designed in F3 of docs/designs/metro-optical/design-brief.md. |
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
