# Skill Gap Reporter Rule Sections

This skill keeps most of its guidance inline in
`SKILL.md`. Only ordering and security-critical
concerns get standalone rule files with eval coverage.

| Prefix | Category | Description |
| ---------- | -------- | ----------- |
| `workflow-` | Workflow | Ordering and gating: the tracker check, triage, and handoff (to `infrahub-reporting-issues`, either for a product defect or to file a skill defect). Skipping one produces noise in the maintainers' tracker or a second, drifting filing pipeline. |
| `evidence-` | Evidence | What may and may not appear in a filed issue. Security-critical: issue bodies are public and cannot be retracted. |
