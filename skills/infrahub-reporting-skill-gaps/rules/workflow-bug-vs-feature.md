---
title: Bug vs. feature vs. docs gap (level 2)
impact: HIGH
tags: workflow, triage, classification, bug, feature, docs-gap, llms-txt
---

## Bug vs. feature vs. docs gap (level 2)

Impact: HIGH

Once level 1 classifies the friction as a skill
defect, decide whether it is a bug, a feature, or a
docs gap before drafting. Use the matching title prefix
in the draft.

### Why it matters

A bug report sends a maintainer to a file that already
exists, expecting to find what is wrong with it. A
feature request sends them to write a new rule citing
documentation that already exists somewhere. A docs-gap
report tells them the documentation itself does not
exist yet, so no rule can cite it until someone writes
it. Mixing these up sends a maintainer looking for a
file that was never written, asks them to patch a file
that was never wrong, or points them at a rule-writing
task when the real blocker is that nobody has written
the underlying documentation.

### What this skill can and cannot see

This skill observes a Claude Code session: what the
model read, ran, and failed at. **It cannot see what a
human read.** "The user didn't have the docs open" is
not a signal available here, and this rule never
pretends otherwise. The discriminator below is built
entirely out of things visible in the transcript.

### The discriminating question

**Does the skill already claim to do this, and if not,
did an escape to the docs resolve it?**

| Evidence | Kind | Repo | Title prefix |
| -------- | ---- | ---- | ------------- |
| A rule or reference covers the topic, and the model still got it wrong | Bug | `opsmill/infrahub-skills` | `bug:` |
| No rule covers it. The model escaped to `docs.infrahub.app`, found the answer, and succeeded | Feature | `opsmill/infrahub-skills` | `feat:` |
| No rule covers it. The model escaped to `docs.infrahub.app` and still failed, or the docs page it reached did not address the problem, and the behavior is settled (see the gate below) | Docs gap | `opsmill/infrahub` | `bug(docs):` |

Feature and docs gap start from the same first sentence
("no rule covers this"). What tells them apart is the
second sentence: what happened after the escape. A
feature report says the knowledge exists somewhere and
the skill just never carried it forward. A docs-gap
report says nobody has written this down anywhere yet,
so the skill cannot cite it until someone does. Put the
exact page path reached, and what it failed to answer,
in the report either way: for a feature it is the
citation a new rule needs, for a docs gap it is the
specification for the documentation that has to be
written first.

Bug and feature both stay inside `opsmill/infrahub-skills`:
the file that needs writing or fixing lives there. A docs
gap leaves it. Infrahub's own documentation lives in
`opsmill/infrahub`, not the skills repo, so a docs-gap
report has to go where the people who maintain that
documentation will actually see it. Filing a docs gap
against the skills repo sends it to maintainers with no
power to fix it, the same mistake
[workflow-handoff-product-bugs.md](workflow-handoff-product-bugs.md)
already guards against for product defects.

This is the same determination
[evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
requires when it asks for the implicated file, so the
two rules check each other. Naming a file means bug.
Finding none means feature or docs gap. If the two
disagree, the citation wins: it is grounded in a file
that either exists or does not, while a felt sense of
"this seems like a bug" is not.

Do not classify by how bad the friction felt. Round
trips, user frustration, and how many times the user
had to nudge the model describe severity, not kind.
Severity belongs in "Where it went wrong" in the
template; it never decides the kind.

### Intent is not a claim

If a rule gestures at the topic but never actually
covers the concrete failure mode that occurred, that is
not a bug. A rule has to address the specific case to
have promised it. A schema rule that discusses
attributes in general, but never mentions enum default
values, has not claimed the enum-default ground; a
model that gets enum defaults wrong against that rule
is looking at a feature or docs gap, not a bug, no
matter how closely the rule's topic sits next to the
failure.

### The settled-behavior gate (docs gap only)

A `bug(docs):` issue asks an Infrahub maintainer to write
down an answer. That is only a fair ask when an answer
already exists to write down: the topic is something
Infrahub genuinely supports, and its behavior is settled.
File `bug(docs):` only under those conditions.

When the workflow itself is still being defined, or is
deliberately left undocumented (an experimental flag, an
internal-only mechanism, a shape still changing release
to release), there is nothing to document yet. Filing
anyway sends a maintainer a request they cannot fulfill,
the same failure mode as filing from a single
uncorroborated session: a report that might not even
describe a stable target. Record an `observed` entry in
the notes file and stop, exactly as the corroboration
gate does when it does not corroborate.

This gate applies to docs gaps only. A bug or a feature
both describe the skill's own guidance, which the skill
can improve regardless of whether Infrahub's own behavior
has finished changing. Only a docs gap asks a second
party, an Infrahub maintainer, to produce something new,
so only a docs gap needs to confirm there is something
settled to produce before asking.

### When no escape happened at all

If the model never escaped to the docs, feature and
docs gap are indistinguishable from the transcript: this
skill has no way to know whether the documentation
covers the topic, because nothing shows what a human
might already know or might find by looking. **Do not
guess.** Default to `feat:`, and say plainly in the
report that no docs escape was observed, so whether the
documentation already covers this topic is unverified. A
maintainer can check a page in seconds; a confidently
wrong claim about docs coverage costs more than an
honest "unverified."

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
reached through it, is close to proof that no rule
covers the topic: the fallback is only authorized once
the skill's own material has already been checked and
found silent. What it does not settle by itself is
whether the kind is feature or docs gap; that depends on
what happened after the fetch, per the table above.

Two cautions:

- **Check the ordering.** An escape that happened
  *before* the model read the skill's own rules is not
  a feature or docs-gap signal. That is the model
  skipping step 1 of the priority rule, a behavior
  defect rather than a skill gap. Only an escape that
  follows a genuine read of the skill's own files
  counts.
- **`marketplace.infrahub.app` and `infrahub.opsmill.io`
  are never escapes.** Several skills instruct fetching
  those URLs as part of their normal workflow. Do not
  read a fetch of either as evidence of a gap.

### Incorrect

```text
bug: infrahub-managing-generators: pagination guidance wrong

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

```text
feat: infrahub-managing-generators: no guidance on multi-hop relationship reads

No rule covers reading an attribute more than one
relationship hop away. I fetched
https://docs.infrahub.app/llms.txt, which pointed at
/guides/graphql/relationships, but that page only
covers single-hop peer reads and never addressed the
multi-hop case; I had to work it out through trial and
error against the GraphQL schema. Filing as a feature
since no rule anywhere covers this.
```

Filed as a feature against `opsmill/infrahub-skills` when
the escape happened and still failed to answer the
question. A maintainer there picks this up expecting to
write a rule that cites `/guides/graphql/relationships`,
and finds that page says nothing about the problem. The
rule they need to write cannot exist yet, because the
documentation it would cite does not exist yet either,
and the skills repo has no power to write Infrahub's own
docs besides. Assuming multi-hop traversal is something
Infrahub genuinely supports today (the settled-behavior
gate above), this is a docs gap, filed against
`opsmill/infrahub` instead: `bug(docs): no documentation
on multi-hop relationship traversal in a GraphQL query`.

### Correct

```text
No rule in patterns-common.md, python-generate.md, or
infrahub-common/graphql-queries.md mentions cursor-based
pagination. I fetched https://docs.infrahub.app/llms.txt
after finishing that read, which pointed at
/guides/graphql/pagination, then fetched that page's
.md twin and found the answer there. The skill's own
files never claimed this ground, so this is a feature:

feat: infrahub-managing-generators: no guidance
on paginating a generator's GraphQL query
```

```text
No rule in patterns-common.md, python-generate.md, or
infrahub-common/graphql-queries.md covers reading an
attribute more than one relationship hop away. I
fetched https://docs.infrahub.app/llms.txt after
finishing that read, which pointed at
/guides/graphql/relationships, and I fetched that
page's Markdown twin too, but it did not address
multi-hop traversal either; the page only covers
single-hop peer reads. I worked it out by reading the
GraphQL schema directly through trial and error.
Multi-hop traversal is something Infrahub genuinely
supports and its behavior is settled, just undocumented,
so the settled-behavior gate is satisfied. Since no rule
covers this and the docs page did not address the case,
this is a docs gap, filed against opsmill/infrahub
rather than the skills repo:

bug(docs): no documentation on multi-hop relationship
traversal in a GraphQL query
```

Reference:
[workflow-information-priority.md](../../infrahub-common/rules/workflow-information-priority.md)
for the fallback procedure this rule consumes;
[evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
for naming the file.
