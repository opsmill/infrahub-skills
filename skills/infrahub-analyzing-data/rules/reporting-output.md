---
title: Compliance Reporting Output
impact: HIGH
tags: reporting, output, findings, remediation
---

## Compliance Reporting Output

Impact: HIGH

Clear, actionable output is what makes compliance
analysis useful. Raw violation lists aren't enough —
findings need context, counts, severity, and
remediation hints. These patterns define how to
present compliance results.

---

### Standard Report Structure

Every compliance report should follow this
structure:

```text
<Title> — <Scope> — <Date>
═══════════════════════════════════
Policy:     <Description of what was checked>
Scope:      <Site / device group / node kind>
Checked:    <N> objects
Compliant:  <N>  (<percentage>%)
Violations: <N>

<Violation Details>

Remediation
───────────
<Actionable next steps>
```

---

### Single-Policy Report

For a focused check on one policy:

```text
Device Naming Convention
  — All Sites — 2026-03-13
══════════════════════════════════════
Policy:     Names must match
            <site><nn>-<role>-<nn>
            (e.g., par01-spine-01)
Checked:    47 devices
Compliant:  43  (91.5%)
Violations: 4

Non-compliant devices:
  ✗ SPINE-01    [id: abc123]
    — uppercase letters,
      missing site prefix
  ✗ spine-01    [id: def456]
    — missing site prefix
  ✗ Leaf_03     [id: ghi789]
    — underscore not allowed,
      mixed case
  ✗ par01-leaf  [id: jkl012]
    — missing sequence number

Remediation
───────────
• Rename affected devices via
  Infrahub UI or:
    mcp__infrahub__infrahub_update(
      kind="DcimDevice",
      id="<id>",
      data={"name": "<correct-name>"}
    )
  Note: always use a branch, not main.
• Consider adding an InfrahubCheck to
  enforce naming on future proposed
  changes.
  See: skills/infrahub-managing-checks/SKILL.md
```

---

### Multi-Policy Summary Report

For a compliance run covering several policies:

```text
Compliance Summary
  — PAR01 — 2026-03-13
════════════════════════════════════
                      Checked Pass Fail Status
────────────────────────────────────────────────
Naming Convention      47      43   4   ⚠ WARN
Interface Desc.       312     298  14   ⚠ WARN
Platform Assignment    47      47   0   ✓ PASS
Loopback IP Space      22      20   2   ⚠ WARN
BGP Peer Count (≥2)     8       8   0   ✓ PASS
────────────────────────────────────────────────
Overall compliance: 416/436 (95.4%)

Details for each ⚠ check are expanded below.
```

---

### Per-Violation Detail Block

Include enough context per violation to act on it
without re-running the analysis:

```text
  ✗ par01-leaf-07 / Loopback0
    Object ID:   17f3a2c4-...
    Kind:        DcimInterface
    Violation:   IP 192.168.100.5/32
                 not in approved loopback
                 prefix 10.0.0.0/24
    Site:        PAR01
    Fix:         Update IP address to a
                 /32 from 10.0.0.0/24
```

Fields to include per violation:

- **Object name** and **ID** (for direct lookup
  or update)
- **Kind** (so the user knows which Infrahub node
  type to navigate to)
- **Violation description** (what policy was
  violated)
- **Suggested fix** (concrete remediation action)

---

### Severity Levels

Not all violations are equal. Use severity markers
to prioritize:

| Symbol | Severity | Meaning |
| ------ | -------- | ------- |
| `✗ CRITICAL` | Critical | Immediate action required (security risk, data loss risk) |
| `✗ ERROR` | Error | Policy violation that must be fixed |
| `⚠ WARN` | Warning | Deviation that should be addressed |
| `ℹ INFO` | Info | Observation, no action required |

Default: use `✗` for all violations unless severity
levels are explicitly requested.

---

### Remediation Hints

Always include a remediation section. Match the
remediation to the violation type:

| Violation Type | Remediation Hint |
| -------------- | ---------------- |
| Missing required attribute | Set value via UI or `mcp__infrahub__infrahub_update` |
| Wrong attribute value | Correct value via UI or `mcp__infrahub__infrahub_update` |
| Missing related object | Create via `mcp__infrahub__infrahub_create` on a branch |
| Naming convention | Rename via UI or update |
| Structural gap (design vs reality) | Run the generator to reconcile, or create manually |
| Recurring pattern | Suggest creating an `InfrahubCheck` to enforce on future changes |

---

### Compact Format for Large Result Sets

When there are many violations, use a compact table
format:

```text
Non-compliant interfaces (14):
Device           Interface  Violation
──────────────────────────────────────────
par01-leaf-01   Eth1/1     Missing desc.
par01-leaf-01   Eth1/2     Missing desc.
par01-leaf-03   Eth1/7     Missing desc.
par01-leaf-05   Eth2/1     Missing desc.
...and 10 more. Use filter
  'site=PAR01, missing_description=true'
  to see all.
```

Limit inline output to 10-15 items; offer to
filter or expand on request.

---

### Exporting Compliance Reports as Artifacts

For repeatable, stakeholder-facing reports, convert
the compliance workflow into a
Transform + Artifact:

```text
Interactive MCP compliance
  → good for ad-hoc, exploratory analysis
InfrahubCheck
  → good for pipeline enforcement (pass/fail)
Transform + Artifact
  → good for scheduled reports, CSV/HTML export
```

See `../infrahub-managing-transforms/SKILL.md` for how to
turn a compliance query into a recurring artifact.

Reference:
[Infrahub Artifact Definitions](https://docs.infrahub.app/topics/artifact)
