---
title: Ask for the bundle location — never deduce it
impact: HIGH
tags: workflow, bundle-location, user-gate
---

## Ask for the bundle location — never deduce it

Impact: HIGH

Before reading anything, ask the user where the
bundle is. Do not scan the filesystem for it, and do
not assume the collector's default output directory.

### Why it matters

The path the analyzer picks decides which incident
gets analyzed. A machine often holds more than one
bundle — repeated collections during the same
outage, older bundles from unrelated incidents, an
extracted copy next to the original archive — and
`./infrahub_bundles/` is only the collector's
default, not where the bundle necessarily lives now.
Deducing the location silently (globbing for
`bundle_information.json`, taking the newest
directory, assuming the default) risks producing a
confident findings report about the wrong incident
or the wrong deployment — worse than no report,
because it sends the user and the expert down a
false trail. Asking costs one question and pins the
analysis to the artifact the user actually means.

### What to do

- Ask the user for the bundle path as the first step
  of the workflow. Offering the default as a hint is
  fine ("commonly `./infrahub_bundles/` if you
  didn't set `--output-dir`"), but the user names
  the path — the skill never picks one.
- After the user answers, validate it: the directory
  should contain `bundle/bundle_information.json`
  (or be the `bundle/` directory itself). If it
  doesn't, say what's missing and ask again rather
  than searching nearby.
- Skip the question only when the location is
  already settled: the user gave a path in their
  request, or they pasted the relevant bundle
  contents directly — re-asking then is friction
  with no gain.
- If the user has no bundle at all, hand off to
  `infrahub-collecting-diagnostics`; do not
  improvise collection.

### Compliant

```text
> Where is the bundle you'd like analyzed? If you
> ran infrahub-collect without --output-dir, it is
> commonly under ./infrahub_bundles/ — paste the
> path and I'll start with its
> bundle_information.json.
```

### Non-compliant

```text
> I'll find it:
find / -name bundle_information.json 2>/dev/null
> Newest match is ./infrahub_bundles/bundle-0712 —
> analyzing that one.
```

Scans the filesystem and silently picks the newest
match — on a host with last week's bundle alongside
today's, the report may describe the wrong outage.

### Common mistakes

- Assuming `./infrahub_bundles/` because it is the
  collector's default — the user may have moved,
  re-collected, or extracted the bundle elsewhere.
- Globbing for `bundle_information.json` and taking
  the newest hit when several bundles exist.
- Validating nothing after the user provides a path
  — a typo'd or half-extracted directory then fails
  later with confusing errors mid-analysis.
- Re-asking for the path when the user already gave
  it (or pasted the contents) — the question is a
  gate, not a ritual.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
