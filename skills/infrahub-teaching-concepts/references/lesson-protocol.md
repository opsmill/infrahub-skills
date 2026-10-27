# Lesson Protocol and Workspace Contract

This file is the single home for the values below. Rules and references
point here instead of restating them. The grader library mirrors them; a
change here without a grader change breaks evals, deliberately.

## The learning workspace

`.infrahub-learning/` in the user's cwd, offered on the first lesson,
never created without consent.

| Path | Role |
| --- | --- |
| `progress.md` | State. Read on resume, updated after each concept. |
| `lessons/<concept>.md` | One durable lesson artifact per concept. |
| `solutions/<concept>.md` | Hidden reference solution plus verification evidence. Written before the exercise is shown. |
| `hints/<concept>.md` | The escalation log. One rung per failed attempt, appended before the hint is given. |

## Concept slugs

`foundations`, `schema`, `objects`, `graphql`, `branches`,
`repo-integration`, `proposed-changes`, `checks`, `transforms`,
`generators`, `menus`.

## Lesson shape

Each lesson file uses exactly these `##` headings, in order:

1. `## Probe`: 2 or 3 questions, each line ending `?`. First session
   includes one background question.
2. `## Explain`: short, anchored to the learner's artifacts, at least one
   `https://docs.infrahub.app/...` link beside the claim it supports.
3. `## Exercise`: assignment line starting `**Your task:**`. Instance
   writes only per the safety rule. No solution content.
4. `## Check`: 1-2 recall or transfer questions, distinct from the probe.

Close the lesson (after `## Check`) with the graduation pointer.

## Solution file shape

`solutions/<concept>.md` holds `## Solution` (the artifact in a code
block) and `## Verification` (the command run and its observed result).

## Progress file shape

Table header, exact: `| concept | status | last-seen | notes |`.
Statuses, exact: `not-seen`, `introduced`, `practiced`.
`last-seen` is an ISO date. A solution reveal keeps the concept at
`introduced`.

## Hint ladder

Failed attempt 1: conceptual hint, no code block over two lines.
Failed attempt 2: concrete pointer (file, field, line).
Failed attempt 3 or learner asks: reference solution with walkthrough.

Every rung is written to `hints/<concept>.md` before it is given, so
the escalation survives the session. Headings, exact: `## Hint 1`,
`## Hint 2`, `## Hint 3`, each holding what the learner was told.
Rungs are appended in order; a `## Hint 3` with no `## Hint 1` above
it is a reveal that skipped the ladder.

## Sandbox branches

Branch names start `learning-`. Consent question before creation.
Cleanup deletes the branch. Never merge it; never write to the default
branch.

## Off-map concepts

A concept with no row in `references/concept-map.md` is taught through
the shared docs fallback defined in
`../../infrahub-common/rules/workflow-information-priority.md` (that
rule owns the lookup mechanics). The resulting lesson uses the same
four-section shape under a new slug of its own (kebab-case, not one of
the eleven above), gets a progress row like any concept, and says the
topic came from the docs fallback. Details in
`../rules/grounding-off-map-lookup.md`.

## Comparison lessons

When the learner frames a question through another tool, the Explain
section carries one line starting exactly `**Comparison source:**`,
whose value is an official competitor docs URL (NetBox:
docs.netbox.dev or netboxlabs.com/docs; Nautobot: docs.nautobot.com) or
the word `unverified`. Details in
`../rules/grounding-competitor-mapping.md`.
