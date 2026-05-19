---
title: Data Correlation Patterns
impact: HIGH
tags: correlation, diffing, joining, policy
---

## Data Correlation Patterns

Impact: HIGH

Correlation is the core step of compliance analysis:
taking data returned from one or more MCP queries
and comparing it against a policy to find violations.
These patterns cover the most common correlation
techniques.

---

### Pattern 1: Membership Check (Allow-list)

Verify each item in "current state" is present in
an approved set.

**Use case:** VLANs on interfaces must be from the
approved VLAN list.

```python
# Build approved set from policy query
approved_vlans = {
    edge["node"]["vlan_id"]["value"]
    for edge in policy_response["IpamVlan"]["edges"]
}

# Check each interface
violations = []
for edge in state_response["DcimInterface"]["edges"]:
    iface = edge["node"]
    vlan_node = iface.get("untagged_vlan", {}).get("node")
    if vlan_node:
        vlan_id = vlan_node["vlan_id"]["value"]
        if vlan_id not in approved_vlans:
            violations.append({
                "device": iface["device"]["node"]["name"]["value"],
                "interface": iface["name"]["value"],
                "vlan": vlan_id,
                "reason": f"VLAN {vlan_id} not in approved list"
            })
```

---

### Pattern 2: Attribute Pattern Match (Regex)

Verify object names or attributes conform to a
naming convention.

**Use case:** Device names must match
`^[a-z]{3}[0-9]{2}-[a-z]+-[0-9]{2}$`.

```python
import re

NAMING_PATTERN = re.compile(r"^[a-z]{3}[0-9]{2}-[a-z]+-[0-9]{2}$")

violations = []
for edge in response["DcimDevice"]["edges"]:
    device = edge["node"]
    name = device["name"]["value"]
    if not NAMING_PATTERN.match(name):
        violations.append({
            "id": device["id"],
            "name": name,
            "reason": f"Does not match pattern <site><nn>-<role>-<nn>"
        })
```

---

### Pattern 3: Relationship Count Threshold

Verify objects have the required number of related
objects.

**Use case:** Spine devices must have at least 2
active BGP sessions.

```python
violations = []
for edge in response["DcimDevice"]["edges"]:
    device = edge["node"]
    active_sessions = [
        s for s in device["bgp_sessions"]["edges"]
        if s["node"]["status"]["value"] == "active"
    ]
    if len(active_sessions) < 2:
        violations.append({
            "id": device["id"],
            "name": device["name"]["value"],
            "active_sessions": len(active_sessions),
            "reason": f"Only {len(active_sessions)} active BGP sessions (min: 2)"
        })
```

---

### Pattern 4: Presence Check (Required Relationship)

Verify a required relationship is present
(not null/empty).

**Use case:** All devices must have a platform
assigned.

```python
violations = []
for edge in response["DcimDevice"]["edges"]:
    device = edge["node"]
    platform = device.get("platform", {}).get("node")
    if not platform:
        violations.append({
            "id": device["id"],
            "name": device["name"]["value"],
            "reason": "No platform assigned"
        })
```

---

### Pattern 5: Cross-Node ID Join

Correlate two node types using a shared identifier
(e.g., IP address, ASN, name).

**Use case:** Every BGP session must have a matching
IP address in IPAM.

```python
# Build IP set from IPAM
ipam_addresses = {
    edge["node"]["address"]["value"].split("/")[0]  # strip prefix length
    for edge in ipam_response["IpamIPAddress"]["edges"]
}

# Check BGP sessions
violations = []
for edge in bgp_response["NetworkBgpSession"]["edges"]:
    session = edge["node"]
    remote_ip = session.get("remote_ip", {}).get("node", {}).get("address", {}).get("value", "")
    remote_ip_addr = remote_ip.split("/")[0] if remote_ip else ""
    if remote_ip_addr and remote_ip_addr not in ipam_addresses:
        violations.append({
            "id": session["id"],
            "name": session["name"]["value"],
            "remote_ip": remote_ip,
            "reason": "Remote IP not found in IPAM"
        })
```

---

### Pattern 6: Symmetric Relationship Check

Verify bidirectional relationships exist
(e.g., BGP sessions must have a reverse).

**Use case:** For every session A->B there must be
a session B->A.

```python
# Build set of (local_device, remote_device) tuples
sessions = set()
for edge in response["NetworkBgpSession"]["edges"]:
    s = edge["node"]
    local = s["device"]["node"]["name"]["value"]
    remote = s.get("remote_device", {}).get("node", {}).get("name", {}).get("value", "")
    if remote:
        sessions.add((local, remote))

# Check for missing reverse
violations = []
for (local, remote) in sessions:
    if (remote, local) not in sessions:
        violations.append({
            "direction": f"{local} → {remote}",
            "reason": f"No reverse session from {remote} → {local}"
        })
```

---

### Pattern 7: Design-to-Reality Diff

Compare expected objects (from a design/template)
against realized objects.

```python
# Expected from design
expected_names = {
    edge["node"]["name"]["value"]
    for edge in design_response["TopologyDevice"]["edges"]
}

# Realized objects
realized_names = {
    edge["node"]["name"]["value"]
    for edge in state_response["DcimDevice"]["edges"]
}

missing = expected_names - realized_names      # in design, not realized
extra   = realized_names - expected_names      # realized, not in design
```

---

### Grouping Violations by Site or Device

When reporting, group violations to make findings
actionable:

```python
from collections import defaultdict

by_site = defaultdict(list)
for v in violations:
    by_site[v.get("site", "unknown")].append(v)

for site, items in sorted(by_site.items()):
    print(f"\nSite: {site} ({len(items)} violation{'s' if len(items) != 1 else ''})")
    for item in items:
        print(f"  ✗ {item['name']} — {item['reason']}")
```

Reference:
[Infrahub Check Examples](../../infrahub-managing-checks/examples.md)
