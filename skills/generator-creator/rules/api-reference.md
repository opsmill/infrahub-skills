---
title: InfrahubGenerator API Reference
impact: HIGH
tags: api, constructor, properties, methods
---

## InfrahubGenerator API Reference

Impact: HIGH

### Constructor Parameters

| Parameter                      | Type   | Default  | Desc               |
| ------------------------------ | ------ | -------- | ------------------ |
| `query`                        | `str`  | required | GraphQL query name |
| `client`                       | Client | required | SDK client         |
| `branch`                       | `str`  | `""`     | Branch name        |
| `root_directory`               | `str`  | `""`     | Repo root path     |
| `params`                       | `dict` | `None`   | Query parameters   |
| `convert_query_response`       | `bool` | `False`  | Convert to objects |
| `execute_in_proposed_change`   | `bool` | `True`   | Run in PC          |
| `execute_after_merge`          | `bool` | `True`   | Run after merge    |

### Instance Properties

| Property              | Type             | Description             |
| --------------------- | ---------------- | ----------------------- |
| `self.client`         | `InfrahubClient` | Tracking-enabled client |
| `self.nodes`          | `list`           | SDK objects (converted) |
| `self.related_nodes`  | property         | Related nodes           |
| `self.store`          | `NodeStore`      | Populated on collection |
| `self.branch`         | `str`            | Current branch name     |
| `self.root_directory` | `str`            | Repository root path    |
| `self.logger`         | `Logger`         | Operation tracking      |
| `self.params`         | `dict`           | Query parameters        |

### Key Methods

| Method                     | Description                 |
| -------------------------- | --------------------------- |
| `async generate(data)`     | Implement this. Your logic. |
| `async collect_data()`     | Runs GraphQL query (auto)   |
| `async run(id, data=None)` | Orchestrates the full run   |

Reference:
[Infrahub SDK Docs](https://docs.infrahub.app)
