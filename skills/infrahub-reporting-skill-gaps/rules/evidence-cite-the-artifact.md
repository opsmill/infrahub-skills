---
title: Cite the artifact
impact: HIGH
tags: evidence, citation, artifact
---

## Cite the artifact

Impact: HIGH

Every skill-defect report names the file the maintainer should open, or
states plainly that no such file exists yet.

### What counts as citing

Only two things satisfy this rule:

- A path under `skills/<skill>/rules/`, or the skill's own
  `skills/<skill>/SKILL.md`, naming the file a maintainer should edit —
  for example
  `skills/infrahub-managing-schemas/rules/relationship-identifiers.md`.
- The sentence "No rule in this skill covers `<topic>`," stating plainly
  that the gap is the absence of a file, not a fault in one that exists.

A vague reference to "the schema skill" or "the generators guidance" does
not count either way. It gives the maintainer a search, not a starting
point.

### Why it matters

The maintainer's first action on a filed report is opening a file. A
report that names one turns that action into a five-minute fix. A report
that only describes symptoms turns it into a search through every rule
file in the implicated skill, repeating the exact investigation step 5 of
this skill's workflow already did.

### Agreement with bug vs. feature

[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md) asks "does the
skill already claim to do this?" and answers it from the classification
side: a rule that covers the topic and still let the model down is a bug,
no coverage anywhere is a feature. This rule asks the same question from
the citation side, and the two must agree. Naming a file means bug.
Finding none means feature. If a draft cites a specific rule file but
titles itself `feat:`, or states no rule covers the topic but titles
itself `bug:`, the two rules disagree and the draft is not ready. Resolve
the disagreement before handing off, and let the citation win: it is
grounded in a file that either exists or does not, not in how the
friction felt.

### Incorrect

```text
bug: infrahub-managing-schemas: relationship cardinality is confusing

The schema skill's guidance on relationships didn't cover this case well
and I had to work it out by trial and error.
```

Names no file. A maintainer looking for what to fix has to re-read every
rule in the schemas skill to find the gap this report is describing.

### Correct

```text
bug: infrahub-managing-schemas: relationship-identifiers.md doesn't
mention the generic-peer case

skills/infrahub-managing-schemas/rules/relationship-identifiers.md
documents the required identifier for a bidirectional relationship, but
never states that a generic peer on either side needs one too. I set up
exactly the case that rule warns about, left the identifier off, and hit
the exact failure it describes.
```

Reference: [workflow-bug-vs-feature.md](workflow-bug-vs-feature.md) for
the bug/feature discriminator this rule shares.
