<!--
Skill-friction template for opsmill/infrahub-skills.
Every bracketed placeholder must be replaced before
this is handed off. Every section except "Proposed rule
change" may be deleted when it does not apply to this
report. Use generic phrasing throughout: no customer
names, node kinds, hostnames, or paths.

Title prefix carries the level-2 classification: bug:
when a rule or reference already covers the topic and
the model still got it wrong, feat: when no rule covers
it and a docs escape either found the answer or never
happened at all, docs: when no rule covers it and a docs
escape happened but still failed to answer the question.
See rules/workflow-bug-vs-feature.md. This title, and
the body below, are handed to infrahub-reporting-issues
as-is; see rules/workflow-handoff-to-reporting.md. Do
not file this directly.

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

# [bug|feat|docs]: [skill]: [what the guidance is missing]

**Skill**: [skill directory, e.g. infrahub-managing-schemas]
**Type**: [bug | feature | docs gap]
**Recurrence**: [number of corroborating sessions, or the explicit user confirmation that stood in for a second session]

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
