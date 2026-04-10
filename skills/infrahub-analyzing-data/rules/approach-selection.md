---
title: Choosing the Right Approach
impact: MEDIUM
tags: approach, mcp, check, transform, decision
---

## Choosing the Right Approach

Impact: MEDIUM

Infrahub offers three distinct ways to analyze data
and surface findings. Picking the right one avoids
over-engineering simple tasks and under-engineering
recurring ones.

---

### Decision Table

| Criterion | MCP Analysis (this skill) | InfrahubCheck | Transform + Artifact |
| --------- | ------------------------- | ------------- | -------------------- |
| **Trigger** | On demand, conversational | Every proposed change | Scheduled or on demand |
| **Enforcement** | None (informational) | Blocks merge on failure | None (output only) |
| **Automation** | Manual (Claude + human) | Fully automated | Fully automated |
| **Output** | Chat response | Pass/fail in pipeline UI | File artifact (JSON/CSV/text) |
| **Setup cost** | Zero | Python + GQL + config | Python/Jinja2 + config |
| **Best for** | Exploration, one-off audits | Ongoing policy enforcement | Recurring reports, exports |

---

### Use MCP Analysis (this skill) when

- You need to answer a one-off question
  ("what's broken right now?")
- You're exploring the data model before writing
  a check or generator
- The policy is informal or still being defined
- You want immediate results without writing code
- The analysis involves reasoning that's hard to
  express as a pure pass/fail rule
- You need to investigate a specific incident or
  change impact

**Example prompts:**

- "Which devices are in the PAR01 maintenance
  window starting tonight?"
- "Show me all BGP sessions missing a
  prefix-list"
- "What services depend on devices in rack
  PAR01-A01?"

---

### Use InfrahubCheck when

- The policy is stable and should be enforced
  automatically
- You want to **block** non-compliant proposed
  changes from merging
- The check needs to run on every change without
  human involvement
- The validation logic can be expressed as
  Python + GraphQL

**Example policies suited to checks:**

- Rack unit collision detection
- Required interface description on all active
  interfaces
- Loopback IP must be from the approved prefix

See `../infrahub-managing-checks/SKILL.md` to implement.

---

### Use Transform + Artifact when

- You need a recurring report (daily, weekly,
  per proposed change)
- Stakeholders need the output as a file
  (CSV, HTML, JSON)
- The report is identical every time it runs,
  just with fresh data
- You want to attach the compliance snapshot to
  a proposed change for review

**Example use cases:**

- Weekly IP address utilization report
- Pre-change device inventory export
- Nightly audit of naming convention violations
  as CSV

See `../infrahub-managing-transforms/SKILL.md` to implement.

---

### Common Escalation Path

Start with MCP analysis to understand the problem,
then escalate:

```text
1. MCP Analysis
   — explore and define the policy interactively
       ↓
2. InfrahubCheck
   — enforce it automatically on proposed changes
       ↓
3. Transform
   — export a recurring report for stakeholders
```

You don't have to go through all three steps —
stop at whichever level of automation is
appropriate.

Reference:
[Infrahub Check Docs](https://docs.infrahub.app/topics/check)
·
[Infrahub Artifact Docs](https://docs.infrahub.app/topics/artifact)
