---
title: Verify Reference Closure Locally Before Branch + Validate
impact: MEDIUM
description: >-
  Before creating the branch, verify every relationship reference in the
  emission resolves to either a row in an upstream emitted file or to an
  existing object the introspection found on the target branch. Orphan
  references fail closed locally — cheaper than waiting for server validate.
tags: workflow, closure, references, pre-flight, local-validation
---

## Verify Reference Closure Locally Before Branch + Validate

Impact: MEDIUM

After emitting all files but before step 10 (create
branch), walk every relationship reference in
`spec.data` rows and verify the target exists either
(a) in an upstream NN-prefixed file, or (b) in the
data the introspection step pulled from the live
server. If a reference points at nothing, fail
closed with a diagnostic before any branch is
touched.

### Why it matters

Without closure check, an orphan reference is
caught later — by `infrahubctl object validate` on
the branch (step 11). At that point a branch
already exists, the user has waited for the round
trip, and the diagnostic is a generic
"reference-not-found" without naming the source
CSV row that produced it.

Local closure check is fast (everything is already
in memory), specific (names the producing CSV row),
and avoids creating a branch that's destined to be
discarded.

### What to check

For every row in every emitted file:

1. Walk each key whose value is a relationship
   reference (scalar HFID string, list HFID, or
   component-children wrapper).
2. Build the set of "emitted HFIDs" by scanning all
   upstream files' `spec.data` for the target
   kind's HFID-determining attribute(s).
3. Build the set of "live HFIDs" from the schema
   introspection's preloaded data, if any was
   captured.
4. For each reference, the resolved HFID must be in
   one of the two sets.

If introspection didn't fetch live data (MCP/CLI/API
unavailable, only local schemas read), skip step 3 —
the check verifies emitted-only closure. Make this
limitation explicit in the closure report.

### Diagnostic shape on failure

```text
Cannot create branch: 2 orphan references detected.

  - 03_devices.yml row 4 (name: edge-01):
      manufacturer = "Cisco"
      No row with name "Cisco" in 01_manufacturers.yml
      No live object found by introspection
      Source: inventory.csv row 5 (manufacturer_name column)

  - 03_devices.yml row 7 (name: spine-03):
      site = ["nyc-1", "rack-A"]
      No row with [shortname="nyc-1", name="rack-A"] in 02_racks.yml
      No live object found by introspection
      Source: inventory.csv row 8 (site_name + rack_name columns)

Options:
  a) Add the missing rows to the source CSV (manufacturers.csv, racks.csv)
  b) Confirm the references match an existing object on the target branch
     (re-run with MCP / infrahubctl available so introspection sees live data)

No branch has been created.
```

### When the check is satisfied vacuously

If the emission contains no cross-file relationships
— a single-kind import like `manufacturers.csv` —
the closure check is a no-op and passes. Record the
no-op in the plan so the user knows it ran.

### Common mistakes

- **Skipping closure because server validate will
  catch it.** Validate runs on a branch that has
  to be created first; the closure check exists to
  avoid that round trip.
- **Comparing on the full reference shape (scalar
  vs list) instead of resolved values.** A scalar
  HFID `Cisco` and a list HFID `[Cisco]` both
  resolve to the same target if the schema's HFID
  is single-element — compare resolved values.
- **Treating a missing live-data set as a closure
  failure.** If introspection couldn't reach the
  server, the closure check is "emitted-only" — a
  reference to a live-only object can't be
  resolved locally but isn't an orphan. Surface
  the limitation, don't fail the check.
- **Re-running the check after each file edit
  during emission.** Run it once, after all files
  are written, just before step 10.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
