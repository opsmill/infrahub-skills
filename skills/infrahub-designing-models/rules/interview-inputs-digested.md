---
title: interview-inputs-digested
impact: CRITICAL
tags: inputs, files, evidence, diagrams, spreadsheets
---

# Rule: interview-inputs-digested

## The rule

Every file the user provides, attached or pasted into
the conversation, is read and appears in the brief:

1. One row in the `## Inputs` table, named as the user
   named it, saying what was taken from it.
2. Each sketch row whose identity, peers or source of
   truth came from a file names that file in its
   `Evidence` cell, as `file:column` or `file:element`.
   A row identified by a spreadsheet column cites that
   spreadsheet. When the identity combines facts from
   several files, such as a console server named by its
   site code from one file and its role from a diagram, cite every
   one of them: `sites.xlsx:site_code; oob-diagram.drawio:cs1/cs2`.

This holds when the user says they already explained
everything and the files can be skipped. The files are
still read; where they disagree with what the user
said, name the conflict and ask, or record it as an open
item.

## Why it matters

A spreadsheet's columns are how the customer identifies
things today, and a diagram shows which peers really
exist. A brief written from the conversation alone loses
both, and the user's description of their own network
is often the part that is out of date. Evidence also
lets the reviewer see which rows rest on data and which
rest on someone's recollection.

## How to apply

- Read column headers and a sample of rows, never a
  whole export.
- From a diagram, take elements as candidate node kinds
  and connections as candidate peers.
- From a document, take goals, pains, named services and
  the customer's vocabulary.
- From another tool's schema, propose the node kind
  mapping and check the Marketplace for a published one.
- Table format and Evidence values:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
## Inputs

| File | Taken from it |
| --- | --- |
| sites.xlsx | site_code identifies each site; country becomes the parent |
| oob-diagram.drawio | Two console servers per site; which device is cabled to each port |
```

```markdown
| F1 | LocationSite | site_code | name, country (imported) | ConsoleServer (many) | Sites sheet | Facilities team | sites.xlsx:site_code |
```

## Incorrect

The user said to skip the files, so they are missing from
Inputs, and the site row cites the conversation instead
of the spreadsheet it came from.

```markdown
## Inputs

none
```

```markdown
| F1 | LocationSite | site_code | name, country (imported) | ConsoleServer (many) | Sites sheet | Facilities team | user |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Skipping files the user called redundant | The data contradicts the description more often than not |
| Listing only the spreadsheet, not the diagram | Peers and cardinality lose their evidence |
| Evidence that names a similar file | A reviewer cannot trace the row |
