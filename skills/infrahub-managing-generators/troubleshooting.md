# Generator Troubleshooting

Reactive reference for when a cascade isn't behaving as expected, or
when verifying a cascade change before declaring it done. These pages
are intentionally outside `rules/` because they describe *how to
investigate*, not assertions about model output.

---

## Symptom → First Check

When a cascade misbehaves, the symptom usually points at exactly one
failure mode. This table maps each symptom to the first check that
narrows the diagnosis. Cascade failures are rarely "the generator
crashed" — they're "the state didn't settle." A structured first-check
cuts the loop of re-reading code looking for typos.

| Symptom | First check |
| --------- | ------------- |
| Downstream never re-runs even after upstream changes | Read the downstream node's stored `checksum.value` — has the upstream actually written it? A `null` value means the upstream generator never reached its save call. |
| Downstream runs every time despite no input change | Hash the *exact* string the generator computes; compare to `checksum.value`. Mismatch means the hash input is non-deterministic (unsorted, set-like, or includes a clock or UUID). |
| Some downstream nodes are stale, others are current ("partial cascade") | Did the upstream generator raise mid-loop? Re-run it and watch its log — the tracking system only commits objects touched before the exception. |
| Cascade triggers itself in a loop | Is the downstream writing to a field the upstream watches? Inspect the target group for the downstream's outputs. |
| Logic change isn't reaching existing downstream state | Was `GENERATOR_VERSION` bumped? Without a version bump, old checksums still match. See [rules/cascade-version-constant.md](./rules/cascade-version-constant.md). |

### Checksum-Trail GraphQL Query

To verify upstream → downstream handoff, query GraphQL directly:

```graphql
query checksumTrail {
  DcimDevice {
    edges {
      node {
        id
        name { value }
        checksum { value }
      }
    }
  }
}
```

A `null` checksum on a node that should have been touched indicates the
upstream generator never reached its save call — partial cascade.

### Debugging Antipatterns

- Assuming the generator *code* is wrong before checking the *data* —
  cascades fail more often because of unstable hash inputs than because
  of broken logic.
- Bumping `GENERATOR_VERSION` to "force a re-run" before understanding
  *why* the cascade isn't settling — masks the bug, doesn't fix it.
- Re-running the upstream by mutating an unrelated field to force a
  trigger — this changes the hash input and triggers a real (but
  spurious) re-cascade, obscuring whatever was originally broken.

---

## Post-Modification Verification Checklist

After modifying a cascade's code or schema, run through this checklist
before declaring the change done. Each item maps to a class of bug
that ships frequently when skipped. Cascade changes that pass locally
on a clean dataset routinely fail in production where existing
checksums and partial state already exist.

- [ ] **All generator instances reach `ready` status** in the Infrahub
  UI or via `infrahubctl generator list`. A stuck `running` or
  `error` status means the generator never completed — investigate
  the log before judging anything downstream.
- [ ] **Counts match expected.** Compare the number of downstream
  objects against the count the upstream design declares. Mismatches
  reveal partial cascades.
- [ ] **Checksums are populated.** Query downstream `checksum.value`
  for every relevant node. `null` means the upstream never wrote it.
- [ ] **Re-run is a no-op.** Trigger the cascade a second time with no
  input change. The downstream should not modify any nodes. Any
  modification on the second run means non-deterministic hash inputs.
- [ ] **No trigger loops.** Confirm the downstream generator is NOT
  triggered by its own outputs. Inspect the target group membership.
- [ ] **`GENERATOR_VERSION` was bumped if logic changed.** Skipping
  the bump leaves existing downstream state on the old logic. See
  [rules/cascade-version-constant.md](./rules/cascade-version-constant.md).
- [ ] **Schema migration didn't break inheritance.** If the schema was
  edited, confirm `GeneratorTarget` is still in `inherit_from` of every
  downstream node. See [rules/cascade-target-inheritance.md](./rules/cascade-target-inheritance.md).

### Verification Antipatterns

- Treating "the generator finished without error" as success — the
  generator can succeed and still leave inconsistent state (partial
  cascade, stale checksums).
- Skipping the no-op re-run check — this is the single most useful
  verification, because it surfaces non-determinism that other tests
  miss.
- Verifying only on a fresh branch — production state has existing
  checksums that interact with your change in ways a clean branch
  doesn't.
