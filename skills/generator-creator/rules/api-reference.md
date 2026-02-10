---
title: InfrahubGenerator API Reference
impact: HIGH
tags: api, constructor, properties, methods
---

## InfrahubGenerator API Reference

**Impact: HIGH**

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | GraphQL query name |
| `client` | `InfrahubClient` | required | SDK client |
| `branch` | `str` | `""` | Branch name (auto-detected from git) |
| `root_directory` | `str` | `""` | Repository root path |
| `params` | `dict` | `None` | Parameters for the query |
| `convert_query_response` | `bool` | `False` | Convert response to SDK objects |
| `execute_in_proposed_change` | `bool` | `True` | Run during proposed changes |
| `execute_after_merge` | `bool` | `True` | Run after merge |

### Instance Properties

| Property | Type | Description |
|----------|------|-------------|
| `self.client` | `InfrahubClient` | Tracking-enabled client for creating/updating objects |
| `self.nodes` | `list[InfrahubNode]` | SDK objects (when `convert_query_response=True`) |
| `self.related_nodes` | property | Related nodes from data processing |
| `self.store` | `NodeStore` | Populated during data collection |
| `self.branch` / `self.branch_name` | `str` | Current branch name |
| `self.root_directory` | `str` | Repository root path |
| `self.logger` | `Logger` | Logger for operation tracking |
| `self.params` | `dict` | Query parameters |

### Key Methods

| Method | Description |
|--------|-------------|
| `async generate(data: dict) -> None` | **You must implement this.** Your generation logic. |
| `async collect_data()` | Executes the GraphQL query (called automatically) |
| `async run(identifier, data=None)` | Orchestrates collection, tracking, and calls `generate()` |

Reference: [Infrahub SDK Docs](https://docs.infrahub.app)
