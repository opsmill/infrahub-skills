---
title: Component Children Nesting
impact: HIGH
tags: children, components, interfaces, modules
---

## Component Children Nesting

Impact: HIGH

Component relationships (interfaces, modules, tenant
membership) carry their children inline under the
relationship name, with `kind` set on the wrapper
when the relationship targets a generic peer.

### Why it matters

Component children are created together with their
parent in a single loader pass — that's how a device
and its interfaces land in one transaction. If the
relationship peer is a generic (for example
`InterfaceGeneric`), the loader can't pick a
concrete schema without a `kind`, and the whole
device record is rejected before any interface is
written. When the relationship peer is already a
concrete kind on the schema side, the loader infers
it; that's why some component blocks legitimately
omit `kind`.

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

Note: when the relationship peer is a concrete kind
on the schema side, the loader can infer the child
type and `kind` on the wrapper is optional.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
