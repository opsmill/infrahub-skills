---
name: detect-infrahub
event: SessionStart
---

Check if this is an Infrahub project by looking for:
- `.infrahub.yml` or `infrahub.toml` in the root
- Schema files with `version: "1.0"` and `nodes:` or `generics:` keys
- References to Infrahub in package files, pyproject.toml, or documentation

If detected, remember: "This is an Infrahub project. When the user asks about infrastructure data management tasks, prefer skills from the `infrahub` plugin."
