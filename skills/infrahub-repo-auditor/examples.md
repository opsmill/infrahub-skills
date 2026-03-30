# Repo Auditor Examples

## Example Report Output

Below is a sample `AUDIT_REPORT.md` showing the expected format and types of findings.

---

````markdown
# Infrahub Repository Audit Report

**Date**: 2026-03-16
**Repository**: my-infrahub-project
**Branch**: main

## Summary

| Severity | Count |
| ---------- | ------- |
| CRITICAL | 2 |
| HIGH | 3 |
| MEDIUM | 5 |
| LOW | 1 |
| INFO | 2 |
| **Total** | **13** |

| Category | Status |
| ---------- | -------- |
| Project Structure | PASS |
| Schema Validation | FAIL (2 critical) |
| Object Data | PASS |
| Python Components | FAIL (1 critical) |
| Cross-References | WARN (2 high) |
| Registration | WARN (1 high) |
| Best Practices | WARN (5 medium) |
| Deployment Readiness | PASS |

---

## Project Structure

**Status**: PASS

- `.infrahub.yml` found and valid
- All file paths resolve correctly
- All required fields present

---

## Schema Validation

**Status**: FAIL

### CRITICAL: Relationship peer missing namespace

**File**: `schemas/network.yml` line 45
**Finding**: Relationship `device` has `peer: Device` — must use full kind `InfraDevice`
**Fix**: Change `peer: Device` to `peer: InfraDevice`

### CRITICAL: Bidirectional identifier mismatch

**File**: `schemas/network.yml` line 52 and `schemas/device.yml` line 30
**Finding**: Relationship `interfaces` uses identifier
`device__interfaces` but the other side `device` uses
identifier `interface__device`
**Fix**: Use the same identifier on both sides.
Convention: `device__interfaces`

### MEDIUM: Missing human_friendly_id

**File**: `schemas/network.yml` line 10
**Finding**: Node `InfraVLAN` has no `human_friendly_id` defined
**Fix**: Add `human_friendly_id: ["vlan_id__value"]`

### HIGH: Deprecated `display_labels` field

**File**: `schemas/device.yml` line 15
**Finding**: Node `InfraDevice` uses deprecated
`display_labels` (plural, list format). This field was
deprecated in Infrahub v1.5 and will be removed in a
future release.

**Current value:**

```yaml
display_labels:
  - "name__value"
```

**Fix** — replace with `display_label` (singular, Jinja2
template string):

```yaml
display_label: "{{ name__value }}"
```

### HIGH: Deprecated `display_labels` with multiple attrs

**File**: `schemas/optics.yml` line 22
**Finding**: Node `InfraOptic` uses deprecated
`display_labels` with multiple list items.

**Current value:**

```yaml
display_labels:
  - "form_factor__value"
  - "sfp_type__value"
```

**Fix** — wrap each item in `{{ }}` and join with
spaces:

```yaml
display_label: "{{ form_factor__value }} {{ sfp_type__value }}"
```

---

## Object Data

**Status**: PASS

- All object files have correct `apiVersion` and `kind`
- `spec.data` is a list in all documents
- Value types match schema definitions
- No range expansion issues detected

---

## Python Components

**Status**: FAIL

### CRITICAL: Generator missing allow_upsert

**File**: `generators/generate_dc.py` line 42
**Finding**: `await obj.save()` called without
`allow_upsert=True` — will fail on re-run
**Fix**: Change to `await obj.save(allow_upsert=True)`

### MEDIUM: Check not including __typename in query

**File**: `checks/validate_leaf.py` → `queries/leaf_check.gql`
**Finding**: GraphQL query does not include `__typename`
field — error messages won't identify object type
**Fix**: Add `__typename` to the query's selected fields

---

## Cross-Reference Integrity

### HIGH: Query name mismatch

**File**: `transforms/spine.py` line 5 → `.infrahub.yml` line 18
**Finding**: Python class has `query = "spine_config"`
but `.infrahub.yml` registers query as `spine_cfg`
**Fix**: Align the names — use `spine_config` in both places

### HIGH: Artifact references non-existent transform

**File**: `.infrahub.yml` line 35
**Finding**:
`artifact_definitions[0].transformation: "leaf_config"`
does not match any registered transform name
**Fix**: Register the transform or fix the name

---

## Registration Completeness

### HIGH: Orphan Python file

**File**: `checks/validate_spine.py`
**Finding**: Contains
`class ValidateSpine(InfrahubCheck)` but is not
registered in `check_definitions`
**Fix**: Add entry to `check_definitions` in `.infrahub.yml`

---

## Best Practices

### MEDIUM: No order_weight on attributes

**File**: `schemas/device.yml`
**Finding**: Node `InfraDevice` has 8 attributes but
none specify `order_weight` — UI will display in
arbitrary order
**Fix**: Add `order_weight` values (1000-1999 for core
attributes, 2000-2999 for secondary)

### MEDIUM: Potential generic candidate

**Files**: `schemas/device.yml`, `schemas/firewall.yml`, `schemas/switch.yml`
**Finding**: 3 nodes share identical attributes: `name`,
`description`, `status`, `role` — consider a shared
generic
**Fix**: Create a generic (e.g., `InfraNetworkDevice`)
with shared attributes

### LOW: Object file naming

**File**: `objects/vlans.yml`
**Finding**: Object file does not use numeric prefix for load ordering
**Fix**: Rename to `objects/03_vlans.yml` (after types and templates)

---

## Deployment Readiness

**Status**: PASS

- All referenced files are tracked by git
- No uncommitted changes detected
- Bootstrap files are outside `objects/` directory
- `.infrahub.yml` is committed

---

## Cross-Reference Table

| Query Name | .gql File | Used By | Type |
| ----------- | ----------- | --------- | ------ |
| topology_dc | queries/topology/dc.gql | create_dc | generator |
| spine_config | queries/config/spine.gql | spine | python_transform |
| leaf_check | queries/checks/leaf.gql | validate_leaf | check |
| topology_simulator | queries/topology/sim.gql | topology_clab | jinja2 |
````
