---
title: Component Children Nesting
impact: HIGH
tags: children, components, interfaces, modules
---

## Component Children Nesting

Impact: HIGH

For Component relationships (interfaces, modules), nest
children inline under the relationship name with `kind`
specified.

**Incorrect -- missing kind on component children:**

```yaml
data:
  - name: "my-switch"
    interfaces:
      data:
        - name: fxp0                  # What kind? Ambiguous!
```

**Correct -- kind specified:**

```yaml
data:
  - name: "my-switch"
    device_type: QFX5220-32CD
    location: PAR-1
    status: active
    interfaces:
      kind: InterfacePhysical         # Specify the component kind
      data:
        - name: fxp0
          role: management
          status: active
        - name: et-0/0/0
          role: core
          status: active
```

### Parent-Child Inline (Non-Hierarchical)

For Component/Parent relationships like TenantGroup/Tenant:

```yaml
spec:
  kind: OrganizationTenantGroup
  data:
    - name: Internal
      tenants:
        data:
          - name: Engineering
          - name: IT
```

Note: Non-hierarchical component children don't always
require `kind` if the schema relationship unambiguously
identifies the child type.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
