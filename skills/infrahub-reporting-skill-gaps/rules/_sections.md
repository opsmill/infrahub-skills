# Skill Gap Reporter Rule Sections

This skill keeps most of its guidance inline in
`SKILL.md`. Only ordering and security-critical
concerns get standalone rule files with eval coverage.

| Prefix | Category | Description |
| ---------- | -------- | ----------- |
| `workflow-` | Workflow | Ordering and gating: corroboration, triage, handoff, duplicate search, consent. Skipping one produces noise in the maintainers' tracker. |
| `evidence-` | Evidence | What may and may not appear in a filed issue. Security-critical: issue bodies are public and cannot be retracted. |
