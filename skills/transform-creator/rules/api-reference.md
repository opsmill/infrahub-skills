---
title: InfrahubTransform API Reference
impact: HIGH
tags: api, class-attributes, properties, methods
---

## InfrahubTransform API Reference

**Impact: HIGH**

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `query` | `str` | **Required.** GraphQL query name |
| `timeout` | `int` | Timeout in seconds (default: 60) |

### Instance Properties

| Property | Type | Description |
|----------|------|-------------|
| `self.client` | `InfrahubClient` | SDK client (branch-aware clone) |
| `self.nodes` | `list[InfrahubNode]` | SDK objects (when `convert_query_response=True`) |
| `self.store` | `NodeStore` | Populated during data collection |
| `self.branch_name` | `str` | Current branch name |
| `self.root_directory` | `str` | Repository root path (for loading templates/files) |
| `self.server_url` | `str` | Infrahub server URL |

### Key Methods

| Method | Description |
|--------|-------------|
| `transform(data: dict) -> Any` | **You must implement this.** Can be sync or async. Returns transformed data. |
| `async collect_data()` | Executes the GraphQL query (called automatically) |
| `async run(data=None)` | Orchestrates collection, processing, and calls `transform()` |

Reference: [Infrahub SDK Docs](https://docs.infrahub.app)
