---
title: Testing Generators
impact: LOW
tags: testing, infrahubctl, commands
---

## Testing Generators

**Impact: LOW (reference)**

### Commands

```bash
# List available generators
infrahubctl generator --list

# Run a generator locally
infrahubctl generator create_dc --branch=my-branch name=dc-topology-1

# Generators also run automatically:
# - When target objects change in proposed changes
# - After branch merges (if execute_after_merge=True)
```

### Debugging Tips

- Use `self.logger` inside `generate()` for operation tracking
- Test with a small design first (1-2 elements) before scaling
- Check that target `CoreGeneratorGroup` exists and has members
- Verify query variables match `parameters` mapping in `.infrahub.yml`

Reference: [Infrahub CLI Docs](https://docs.infrahub.app)
