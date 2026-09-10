---
title: Run the Bundled Scripts, Do Not Hand-Roll Them
impact: CRITICAL
tags: workflow, scripts, correctness
---

## Run the Bundled Scripts, Do Not Hand-Roll Them

Impact: CRITICAL

Converting NetBox definitions and exporting them from a
live instance are done by the scripts in `scripts/`.
Writing equivalent logic inline is the single easiest
way to produce output that looks right and is not.

### Why it matters

Both tasks look like an afternoon of `yaml.safe_load`
and a loop. They are not, and the gap does not announce
itself: hand-rolled output parses, loads, and is wrong
in ways nobody notices until the data is in production.

Every one of these was found by running the real thing
against the real corpus, and every one is silently lost
by a reimplementation:

| Trap | What a hand-roll does |
| ---- | --------------------- |
| Infrahub has no float attribute kind | Emits `weight: 7.59`, which cannot load into a `Number` |
| Two NetBox lists can share one Infrahub relationship | Second mapping overwrites the first — 108 templates expected, 4 emitted |
| Unique attributes are absent from templates | Concludes a node "cannot be templated" and stops |
| `{module}` is unresolvable at conversion time | Invents a bay position, or drops the port |
| pynetbox lazy-fetches unknown attributes | One HTTP request per nested object, thousands against a live NetBox |
| NetBox choice fields are `{value, label}` | Writes `type: {'value': ...}` into the YAML |

The scripts also produce the coverage report, which is
the skill's mechanism for making loss visible. A
hand-rolled conversion has no report, so the losses are
not merely unfixed — they are unstated.

### What to do

```bash
# from a running NetBox
python scripts/netbox_export_device_types.py --url ... --output-dir ./netbox-export

# from library YAML, whether cloned or exported above
python scripts/netbox_to_infrahub_templates.py ./netbox-export/device-types \
  --mapping scripts/mappings/<profile>.yml --output-dir ./generated

# resolve {module} once modules are installed in bays
infrahubctl generator module_ports --branch <branch>
```

When a schema does not fit, the answer is a **mapping
profile**, not a different script. The profile is the
designed extension point; reaching past it means
reimplementing everything above.

### When writing code *is* right

Reach for the scripts first, but they are not sacred:

- A NetBox or Infrahub concept neither script models —
  racks, cabling, IPAM — is genuinely new work.
- A bug in a script is fixed in the script, with a test,
  not worked around inline.
- Reading data for analysis, rather than producing
  loadable objects, has no correctness contract to lose.

The line is whether the output is meant to load into
Infrahub. If it is, it goes through the scripts.

### Common mistakes

- **"The script does not support my schema, so I will
  write my own."** It does — through the mapping
  profile. See
  [mapping-profile-driven.md](./mapping-profile-driven.md).
- **Reimplementing the export with `curl` and `jq`**
  because it is only a couple of endpoints. It is ten
  endpoints, four shape mismatches, and an N+1 trap.
- **Treating a clean-looking run as success.** The
  coverage report is the evidence. No report, no
  evidence.
