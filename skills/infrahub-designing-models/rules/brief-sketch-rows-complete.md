---
title: brief-sketch-rows-complete
impact: HIGH
tags: brief, sketch, identity, source-of-truth, owner, open-items
---

# Rule: brief-sketch-rows-complete

## The rule

Every row of the data model sketch has a value in
`Identified by`, `Source of truth` and `Owner`. A value
nobody knows is written `open: O<n>`, and `O<n>` exists
in `## Open items` with who might own the answer.

`TBD`, `?`, `unknown`, `-`, a bare `open`, and a value
you made up all fail. When the user asks you to "fill in
sensible defaults", a default you chose is a
recommendation they have not accepted: put it in the
open item as a proposal, not in the sketch as a fact.

## Why it matters

These three columns are where data models fail in
production. Without an identity, imports create
duplicates. Without a source of truth, two systems
overwrite each other. Without an owner, nobody fixes the
data when it is wrong. An invented value looks decided,
so nobody asks the question again; an open item stays
visible until someone answers it.

## How to apply

- Ask about identity, source of truth and owner for
  every node kind before writing the row.
- Number open items `O1`, `O2`, ... and reference them
  from the cell they block.
- Format:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
| F1 | OpticalChannel | channel number | frequency (pool) | Strand (two) | Infrahub | open: O1 | answer Q5 |
```

```markdown
## Open items

- O1: Who owns the channel plan? (owner: unknown, optical or planning team). Proposed: optical team.
```

## Incorrect

The user did not know who owns the channel plan, and the
brief invented an owner.

```markdown
| F1 | OpticalChannel | channel number | frequency (pool) | Strand (two) | Infrahub | Optical team | answer Q5 |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| `TBD` in a cell | Nobody is asked, and nothing tracks it |
| `open: O3` with no O3 entry | The reference points nowhere |
| An open item placed on a different row than the unknown value | The unknown value is still invented |
