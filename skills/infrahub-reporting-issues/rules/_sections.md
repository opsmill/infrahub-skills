# Issue Reporter Rule Sections

This skill keeps most of its guidance inline in
`SKILL.md`. Only security-critical concerns get
standalone rule files with eval coverage.

| Prefix | Category | Description |
| ------ | -------- | ----------- |
| `env-` | Environment info | What can and cannot appear in issue bodies. Security-critical: bad redaction leaks internal infrastructure to public GitHub. |
