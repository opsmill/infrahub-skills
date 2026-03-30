---
title: InfrahubTransform API Reference
impact: HIGH
tags: api, class-attributes, properties, methods
---

## InfrahubTransform API Reference

**Impact:** HIGH

### Class Attributes

| Attribute | Type  | Description                      |
| --------- | ----- | -------------------------------- |
| `query`   | `str` | **Required.** GraphQL query name |
| `timeout` | `int` | Timeout in seconds (default: 60) |

### Instance Properties

- `self.client` -- `InfrahubClient`, SDK client
- `self.nodes` -- `list[InfrahubNode]`, SDK objects
- `self.store` -- `NodeStore`, populated by collect
- `self.branch_name` -- `str`, current branch name
- `self.root_directory` -- `str`, repo root path
- `self.server_url` -- `str`, Infrahub server URL

### Key Methods

| Method                   | Description                       |
| ------------------------ | --------------------------------- |
| `transform(data) -> Any` | **Implement this.** Sync or async |
| `async collect_data()`   | Executes query (auto-called)      |
| `async run(data=None)`   | Orchestrates and calls transform  |

Reference: [Infrahub SDK Docs](https://docs.infrahub.app)
