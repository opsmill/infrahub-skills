---
title: InfrahubTransform API Reference
impact: HIGH
tags: api, class-attributes, properties, methods
---

## InfrahubTransform API Reference

Impact: HIGH

The base class exposes a small surface area: one
required `query` class attribute, a handful of
instance properties populated by the SDK, and a
single method to implement.

### Why it matters

Most transform errors trace back to misusing this
surface: shadowing `self.client` or `self.store` in
`__init__`, omitting the `query` attribute (which
makes the SDK skip data collection entirely and call
`transform(None)`), or overriding `run()` and losing
the orchestration that calls `collect_data()` first.
Reading the table below before writing custom `async`
plumbing usually saves a round trip — the SDK already
runs the query, hydrates `self.nodes`, and hands the
parsed response to `transform()`.

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
