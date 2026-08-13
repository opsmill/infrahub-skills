<!--
Skill-friction template. A bug or feature report targets
opsmill/infrahub-skills; a docs-gap report targets
opsmill/infrahub instead, see the routing note below.
Every bracketed placeholder must be replaced before
this is handed off. Every section except "Proposed rule
change" may be deleted when it does not apply to this
report. Use generic phrasing throughout: no customer
names, node kinds, hostnames, or paths.

Title prefix carries the level-2 classification: bug:
when a rule or reference already covers the topic and
the model still got it wrong, feat: when no rule covers
it and a docs escape either found the answer or never
happened at all, bug(docs): when no rule covers it, a
docs escape happened but still failed to answer the
question, AND the underlying behavior is settled (the
settled-behavior gate; if it is not, do not draft at all,
see rules/workflow-bug-vs-feature.md). See
rules/workflow-bug-vs-feature.md. This title, and the
body below, are handed to infrahub-reporting-issues
as-is; see rules/workflow-handoff-to-reporting.md. Do
not file this directly.

bug: and feat: both target opsmill/infrahub-skills.
bug(docs): targets opsmill/infrahub instead, since
Infrahub's own documentation lives there, and its title
drops the [skill] segment: `bug(docs): [what the
documentation is missing]`, with no skill name, since
that context means nothing to opsmill/infrahub's
maintainers.

For a feature, "Docs the model had to leave the skill
for" is the most useful section: the fetched page paths
are the specification for the rule a maintainer needs
to write. For a bug, "Rules consulted" carries the
weight: it names the file that claimed the ground and
still let the model down. For a docs gap, "Docs the
model had to leave the skill for" carries the weight
again, but the other way around: record which pages were
reached and specifically what they failed to answer,
since that is the specification for the documentation
that needs writing before any rule can cite it.
-->

# [bug|feat]: [skill]: [what the guidance is missing]
<!-- For a docs gap instead, drop the [skill] segment:
`bug(docs): [what the documentation is missing]`. -->

**Skill**: [skill directory, e.g. infrahub-managing-schemas]
**Type**: [bug | feature | docs gap]
**Repo**: [opsmill/infrahub-skills for bug/feature | opsmill/infrahub for docs gap]
**Confidence**: [recurring | unconfirmed single observation]
<!-- Set from the step 2 tracker check. `recurring` when the
user confirmed this has happened before; `unconfirmed single
observation` otherwise. Never omit this line: it is what
lets a maintainer weigh the report, and what lets a second
observer recognize their own case in it. See
rules/workflow-tracker-first.md. -->
**Tracker search**: [the query run against opsmill/infrahub-skills, and its result]

## What was being attempted

<!-- One or two sentences, in generic terms. Describe the
task category, not the specific data. -->

## Rules consulted

<!-- List the rule files that were read before the friction
occurred, or state "No rule in this skill covers the
topic." -->

## Where it went wrong

<!-- A redacted paraphrase of the error or confusion, plus
the round-trip count and the number of user nudges it
took to recover. -->

## Docs the model had to leave the skill for

<!-- Any external doc fetched (docs.infrahub.app,
schema.infrahub.app) because the skill's own content
was insufficient. Omit if none. -->

## What finally worked

<!-- The fix that resolved the friction, in full. This
section is fillable now, not left as a placeholder for
maintainers. -->

## Proposed rule change

<!-- Mandatory. Name the exact rule file to create or edit
under skills/<skill>/rules/, and state specifically what
it should say. Be specific enough that a maintainer can
implement it without guessing at the missing detail. -->
