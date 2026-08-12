---
title: Bug vs. feature (level 2)
impact: HIGH
tags: workflow, triage, classification, bug, feature, llms-txt
---

## Bug vs. feature (level 2)

Impact: HIGH

Once level 1 classifies the friction as a skill
defect, decide whether it is a bug or a feature before
drafting. Use the matching title prefix in the draft.

### Why it matters

A bug report sends a maintainer to a file that already
exists, expecting to find what is wrong with it. A
feature request sends them to write a new one. Mixing
the two up sends a maintainer looking for a file that
was never written, or asks them to patch a file that
was never wrong in the first place.

### The discriminating question

**Does the skill already claim to do this?**

| Answer | Kind | Title prefix |
| ------ | ---- | ------------- |
| A rule or reference covers the topic, and the model still got it wrong | Bug | `[skill-bug]` |
| No rule or reference covers the topic | Feature | `[skill-feature]` |

This is the same determination
[evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
requires when it asks for the implicated file, so the
two rules check each other. Naming a file means bug.
Finding none means feature. If the two disagree, the
citation wins: it is grounded in a file that either
exists or does not, while a felt sense of "this seems
like a bug" is not.

Do not classify by how bad the friction felt. Round
trips, user frustration, and how many times the user
had to nudge the model describe severity, not kind.
Severity belongs in "Where it went wrong" in the
template; it never decides bug vs. feature.

### The llms.txt signal

[workflow-information-priority.md](../../infrahub-common/rules/workflow-information-priority.md)
already tells every Infrahub skill to fall back to
`https://docs.infrahub.app/llms.txt` only when "the
answer is genuinely absent" from the active skill's own
files and the shared `infrahub-common/` references, and
to say so explicitly "so the gap can be filled in a
skill later." That rule has been emitting a gap signal;
this rule is its consumer.

A fetch of `llms.txt`, or of a `docs.infrahub.app` page
reached through it, is close to proof of a feature. The
fallback is only authorized once the skill's own
material has already been checked and found silent, so
seeing the fallback fire is close to seeing the "no rule
covers this" box already ticked. Put the exact page
path in the issue: it is the specification for the rule
a maintainer needs to write.

Two cautions:

- **Check the ordering.** An escape that happened
  *before* the model read the skill's own rules is not
  a feature signal. That is the model skipping step 1
  of the priority rule, a behavior defect rather than a
  skill gap. Only an escape that follows a genuine read
  of the skill's own files counts.
- **`marketplace.infrahub.app` and `infrahub.opsmill.io`
  are never escapes.** Several skills instruct fetching
  those URLs as part of their normal workflow. Do not
  read a fetch of either as evidence of a gap.

### Incorrect

```text
[skill-bug] infrahub-managing-generators: pagination guidance wrong

No rule in this skill's rules/ or in infrahub-common
mentions cursor-based pagination for a generator's
GraphQL query, so I had to work it out from the docs.
Filing as a bug since it took several tries to get
right.
```

Filed as a bug when no rule ever covered the topic. A
maintainer opens the issue looking for the broken file
and finds nothing to fix, because nothing was ever
written.

### Correct

```text
No rule in patterns-common.md, python-generate.md, or
infrahub-common/graphql-queries.md mentions cursor-based
pagination. I fetched https://docs.infrahub.app/llms.txt
after finishing that read, which pointed at
/guides/graphql/pagination, then fetched that page's
.md twin and found the answer there. The skill's own
files never claimed this ground, so this is a feature:

[skill-feature] infrahub-managing-generators: no guidance
on paginating a generator's GraphQL query
```

Reference:
[workflow-information-priority.md](../../infrahub-common/rules/workflow-information-priority.md)
for the fallback procedure this rule consumes;
[evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
for naming the file.
