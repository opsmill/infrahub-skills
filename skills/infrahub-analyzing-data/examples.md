# Infrahub Analyst Examples

Real-world analysis and correlation patterns using
the Infrahub MCP server.

---

## 1. Device Naming Convention Compliance

Verify all devices follow the naming standard
`<site>-<role>-<number>`
(e.g., `par01-spine-01`).

### Step 1 — Query all devices

```graphql
query DeviceNamingCompliance {
  DcimDevice {
    edges {
      node {
        id
        display_label
        name { value }
        role { value }
        site {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

Use `mcp__infrahub__infrahub_query` with the
above query.

### Step 2 — Correlate against policy

Claude evaluates each device name against the
pattern `^[a-z]{3}[0-9]{2}-[a-z]+-[0-9]{2}$`:

```text
COMPLIANT:   par01-spine-01, lon02-leaf-03
VIOLATION:   SPINE-01 (uppercase),
             spine-01 (missing site prefix)
```

### Step 3 — Report findings

```text
Naming Convention Compliance Report
────────────────────────────────────
Policy:      <site><nn>-<role>-<nn>
             (e.g., par01-spine-01)
Checked:     47 devices
Compliant:   43
Violations:  4

Non-compliant devices:
  ✗ SPINE-01  [id: abc123]
    — uppercase, missing site prefix
  ✗ spine-01  [id: def456]
    — missing site prefix
  ✗ Leaf_03   [id: ghi789]
    — underscore not allowed
  ✗ par01-leaf  [id: jkl012]
    — missing sequence number

Remediation: Rename via Infrahub UI or use
mcp__infrahub__infrahub_update
```

---

## 2. VLAN Assignment Compliance

Verify all VLANs in use on devices are from the
approved VLAN list stored in Infrahub.

### Step 1 — Query approved VLANs

```graphql
query ApprovedVlans {
  IpamVlan(status__value: "active") {
    edges {
      node {
        id
        name { value }
        vlan_id { value }
        site {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

### Step 2 — Query VLANs in use on interfaces

```graphql
query InterfaceVlans {
  DcimInterface {
    edges {
      node {
        id
        name { value }
        mode { value }
        untagged_vlan {
          node {
            vlan_id { value }
            name { value }
          }
        }
        tagged_vlans {
          edges {
            node {
              vlan_id { value }
              name { value }
            }
          }
        }
        device {
          node {
            name { value }
            site {
              node {
                name { value }
              }
            }
          }
        }
      }
    }
  }
}
```

### Step 3 — Cross-reference

Build the approved VLAN set per site, then check
each interface's VLANs against that set:

```text
VLAN Compliance Report
──────────────────────
Site: PAR01
  Approved VLANs: 10, 20, 30, 100, 200
  Interfaces checked: 128
  Compliant: 124
  Violations: 4

  Non-compliant interfaces:
    ✗ par01-leaf-01 / Eth1/10
      — VLAN 999 not in approved list
    ✗ par01-leaf-02 / Eth1/5
      — VLAN 50 not in approved list
    ...
```

---

## 3. BGP Peer Correlation

Verify each BGP session has a matching IP
prefix-list for route filtering, and that the
peer AS matches the expected ASN from the
neighbor's device record.

### Step 1 — Query BGP sessions

```graphql
query BgpSessions {
  NetworkBgpSession {
    edges {
      node {
        id
        display_label
        name { value }
        status { value }
        local_as {
          node {
            asn { value }
          }
        }
        remote_as {
          node {
            asn { value }
          }
        }
        local_ip {
          node {
            address { value }
          }
        }
        remote_ip {
          node {
            address { value }
          }
        }
        prefix_lists {
          edges {
            node {
              name { value }
              direction { value }
            }
          }
        }
        device {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

### Step 2 — Compliance checks

Claude evaluates each session:

| Check | Policy |
| ----- | ------ |
| Prefix lists present | Each active session must have ≥1 import and ≥1 export prefix-list |
| Session symmetry | For every session on device A to device B, a reverse session must exist |
| Status | All sessions with `status: active` must have both sides configured |

### Step 3 — Report

```text
BGP Session Compliance Report
──────────────────────────────
Sessions checked: 24
Fully compliant: 19
Violations: 5

Missing prefix-lists (3):
  ✗ par01-spine-01 → lon02-spine-01
    — no import prefix-list
  ✗ par01-spine-02 → lon02-spine-01
    — no export prefix-list
  ✗ par01-leaf-03 → par01-spine-01
    — no prefix-lists at all

Asymmetric sessions (2):
  ✗ par01-leaf-05 → par01-spine-02
    — no reverse session found
      on par01-spine-02
  ✗ lon02-leaf-01 → lon02-spine-03
    — reverse session exists but
      status: disabled
```

---

## 4. IP Address Space Compliance

Verify all device loopback IPs are allocated from
the approved loopback prefix, and identify any
rogue IPs.

### Step 1 — Query approved prefix

```graphql
query LoopbackPrefix {
  IpamPrefix(role__value: "loopback") {
    edges {
      node {
        id
        prefix { value }
        site {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

### Step 2 — Query assigned loopback IPs

```graphql
query LoopbackIPs {
  DcimInterface(name__value: "Loopback0") {
    edges {
      node {
        id
        ip_addresses {
          edges {
            node {
              id
              address { value }
            }
          }
        }
        device {
          node {
            name { value }
            site {
              node {
                name { value }
              }
            }
          }
        }
      }
    }
  }
}
```

### Step 3 — Validate containment

Claude checks each loopback IP is contained within
the approved prefix for its site:

```text
IP Space Compliance Report
───────────────────────────
Approved loopback prefix:
  10.0.0.0/24 (site: PAR01)
Loopback IPs checked: 22
Compliant: 20
Violations: 2

Rogue IPs (not in approved prefix):
  ✗ par01-leaf-07 / Loopback0
    — 192.168.100.5/32
      (not in 10.0.0.0/24)

Missing loopbacks
(devices with no Loopback0):
  ✗ par01-leaf-09
    — no Loopback0 interface found
```

---

## 5. Design-to-Reality Correlation

Verify that generator-created objects match their
design intent by comparing design nodes to
realized objects.

### Step 1 — Query topology designs

```graphql
query TopologyDesigns {
  TopologyTopology {
    edges {
      node {
        id
        name { value }
        description { value }
        devices {
          edges {
            node {
              name { value }
              role { value }
              device_type {
                node {
                  name { value }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Step 2 — Query realized devices

```graphql
query RealizedDevices($topology: String!) {
  DcimDevice(topology__name__value: $topology) {
    edges {
      node {
        id
        name { value }
        role { value }
        device_type {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

### Step 3 — Diff design vs reality

```text
Design Compliance Report:
  topology-par01-core
──────────────────────────────────────────
Expected devices: 6 (2 spines, 4 leafs)
Realized devices: 5

Missing from reality:
  ✗ par01-leaf-04
    (role: leaf, type: Arista7050CX3)

Extra in reality (not in design):
  ✗ par01-mgmt-01 (role: management)
    — not defined in topology design

Device type mismatches:
  ✗ par01-leaf-02
    — expected: Arista7050CX3,
      actual: Arista7280CR3
```

---

## 6. Maintenance Window Impact Analysis

Find all devices currently in an active maintenance
window and surface which services and BGP sessions
are affected.

### Step 1 — Query active maintenance windows

```graphql
query ActiveMaintenanceWindows {
  MaintenanceWindow(status__value: "active") {
    edges {
      node {
        id
        name { value }
        start_time { value }
        end_time { value }
        devices {
          edges {
            node {
              id
              name { value }
              role { value }
              site {
                node { name { value } }
              }
            }
          }
        }
      }
    }
  }
}
```

### Step 2 — Query services hosted on those devices

```graphql
query DeviceServices($device: String!) {
  ServiceInstance(
    device__name__value: $device
  ) {
    edges {
      node {
        id
        name { value }
        status { value }
        service_type { value }
        customers {
          edges {
            node {
              name { value }
            }
          }
        }
      }
    }
  }
}
```

Run this query for each device found in Step 1.

### Step 3 — Report

```text
Maintenance Window Impact Report
  — 2026-03-13 14:00 UTC
══════════════════════════════════
Active windows: 1

  Window: MW-2026-03-13-PAR01-CORE
  Period: 2026-03-13 14:00 → 18:00 UTC
  Devices in scope: 2

  par01-spine-01 (spine, PAR01)
    BGP sessions:    4 active
                     (will be impacted)
    Services:        3
      • SVC-MPLS-CustA  [active]
        — Customer: Acme Corp
      • SVC-MPLS-CustB  [active]
        — Customer: Globex
      • SVC-INTERNET-01 [active]
        — Customer: Initech

  par01-spine-02 (spine, PAR01)
    BGP sessions:    4 active
                     (will be impacted)
    Services:        1
      • SVC-INTERNET-02 [active]
        — Customer: Initech

  ─────────────────────────────────
  Total affected services: 4
  Total affected customers: 3
    (Acme Corp, Globex, Initech)
  Recommendation: Notify affected
    customers before window starts.
```

---

## 7. Service Impact Analysis for a Planned Change

Before changing a prefix or interface, identify
everything that depends on it.

### Step 1 — Query the prefix and its consumers

```graphql
query PrefixImpact($prefix: String!) {
  IpamPrefix(prefix__value: $prefix) {
    edges {
      node {
        id
        prefix { value }
        role { value }
        ip_addresses {
          edges {
            node {
              id
              address { value }
              interface {
                node {
                  name { value }
                  device {
                    node {
                      name { value }
                      role { value }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Step 2 — Report blast radius

```text
Change Impact Analysis
  — Prefix 10.0.1.0/24
════════════════════════════════════
Role:    transit
Status:  active

IP addresses allocated: 6
  10.0.1.1/30
    → par01-spine-01 / Eth1/1
  10.0.1.2/30
    → lon02-spine-01 / Eth1/1 (peer)
  10.0.1.5/30
    → par01-spine-01 / Eth1/2
  10.0.1.6/30
    → lon02-spine-02 / Eth1/1 (peer)
  ...

BGP sessions using IPs from this prefix: 4
Services riding these BGP sessions: 7

⚠ Changing or withdrawing this prefix
  will affect 4 BGP sessions and
  potentially 7 services. Create a
  maintenance window and notify affected
  customers before proceeding.
```

---

## 8. Multi-Check Analysis Run

Run several analysis checks in sequence and
produce a consolidated report.

### Prompt pattern

```text
Run a full analysis for site PAR01. Check:
1. Device naming convention
   (<site><nn>-<role>-<nn>)
2. All active interfaces have a description
3. All devices have a platform assigned
4. All loopback IPs are from the approved
   10.0.0.0/24 prefix
```

Claude will:

1. Run `mcp__infrahub__infrahub_query` once per
   area (or combine into fewer queries)
2. Evaluate each check independently
3. Produce a consolidated summary

### Consolidated report format

```text
Analysis Summary — PAR01 — 2026-03-13
──────────────────────────────────────
                          Checked Pass Fail Status
──────────────────────────────────────────────────
Naming Convention          47      43   4   ⚠ WARN
Interface Descriptions    312     298  14   ⚠ WARN
Platform Assignment        47      47   0   ✓ PASS
Loopback IP Space          22      20   2   ⚠ WARN
──────────────────────────────────────────────────
Overall: 408/428 (95.3%)

See detailed findings above for remediation steps.
```

---

## Complete MCP Tool Invocation Reference

| Scenario | MCP Tool | Key Arguments |
| -------- | -------- | ------------- |
| Query objects | `mcp__infrahub__infrahub_query` | `query` (GraphQL string) |
| List schema kinds | `mcp__infrahub__infrahub_list_schema` | none |
| Get one object | `mcp__infrahub__infrahub_get` | `kind`, `id` or filters |
| Update for remediation | `mcp__infrahub__infrahub_update` | `kind`, `id`, `data` |
| Create missing object | `mcp__infrahub__infrahub_create` | `kind`, `data` |
