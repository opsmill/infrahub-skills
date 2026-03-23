---
title: InfrahubGenerator API Reference
impact: HIGH
tags: api, constructor, properties, methods
---

## InfrahubGenerator API Reference

Impact: HIGH

### Constructor Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | `str` | required | GraphQL query name |
| `client` | Client | required | SDK client |
| `branch` | `str` | `""` | Branch name (auto-detected from git) |
| `root_directory` | `str` | `""` | Repo root path |
| `params` | `dict` | `None` | Query parameters |
| `convert_query_response` | `bool` | `False` | Convert response to InfrahubNode objects |
| `execute_in_proposed_change` | `bool` | `True` | Run in Proposed Change |
| `execute_after_merge` | `bool` | `True` | Run after merge |

### Instance Properties

| Property | Type | Description |
| --- | --- | --- |
| `self.client` | `InfrahubClient` | Tracking-enabled client |
| `self.nodes` | `list[InfrahubNode]` | Converted SDK node objects (populated when `convert_query_response=True`) |
| `self.related_nodes` | `list[InfrahubNode]` | Nodes sharing the same parent or group relationship as the target |
| `self.store` | `NodeStore` | Populated on collection |
| `self.branch` | `str` | Current branch name |
| `self.root_directory` | `str` | Repository root path |
| `self.logger` | `Logger` | Operation tracking |
| `self.params` | `dict` | Query parameters |

### Key Methods

| Method | Description |
| --- | --- |
| `async generate(data: dict) -> None` | Override this method to implement Generator logic |
| `async collect_data()` | Executes the GraphQL query automatically |
| `async run(identifier: str, data: dict \| None = None)` | Orchestrates the full Generator run |

Reference:
[Infrahub SDK Docs](https://docs.infrahub.app)
