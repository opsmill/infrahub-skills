---
name: skill-pipeline-common
description: >-
  Shared references for the skill-change pipeline: the handoff file format and
  the ground truth ladder. DO NOT TRIGGER directly. The four pipeline stages
  link these files when they need them, and nothing else should.
user-invocable: false
metadata:
  internal: true
  pipeline: "skill-change (shared references, not a stage)"
  version: 0.1.0
  author: OpsMill
---

# Skill Pipeline Common References

Shared resources for the four stages of the skill-change pipeline. Not a stage,
and not invoked directly.

Both files exist because more than one stage needs the same fact. The handoff
format is written by the two entrances and read by the two stages after them;
the ground truth ladder is run by both entrances. Four copies of either would
drift, which is what
[`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
rung 2 is about.

## Contents

- **[`handoff-format.md`](./handoff-format.md)** — the `.skill-change-<key>.md`
  file: how the key is derived, the template, the required fields, and the
  default-branch snippet every stage re-derives.
- **[`ground-truth.md`](./ground-truth.md)** — verifying a claim about Infrahub
  behavior against real source at a version, and deciding whether the behavior
  was already fixed upstream.

## Who reads what

| File | Written by | Read by |
| --- | --- | --- |
| `handoff-format.md` | `analyzing-skill-bugs`, `grilling-skill-features` | `test-driving-skill-changes`, `implementing-skill-changes` |
| `ground-truth.md` | nobody, it is a procedure | both entrance stages |
