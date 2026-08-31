# Infrahub Transform Examples

Real-world examples extracted from production Infrahub repositories.

## Contents

- [1. Python Transform with Jinja2 Rendering (Spine Config)](#1-python-transform-with-jinja2-rendering-spine-config)
- [2. CSV Cable Matrix Transform](#2-csv-cable-matrix-transform)
- [3. Jinja2 Transform (ContainerLab Topology)](#3-jinja2-transform-containerlab-topology)
- [4. Minimal Python Transform Template](#4-minimal-python-transform-template)
- [5. Shared Transform Utilities](#5-shared-transform-utilities)
- [6. SVG Diagram Artifact (`image/svg+xml`)](#6-svg-diagram-artifact-imagesvgxml)
- [Complete File Structure](#complete-file-structure)

---

## 1. Python Transform with Jinja2 Rendering (Spine Config)

A Python Transformation that prepares data and renders a
platform-specific Jinja2 template.

### Query: `queries/config/spine.gql`

```graphql
query spine_config($device: String!) {
  DcimDevice(name__value: $device) {
    edges {
      node {
        id
        name { value }
        role { value }
        device_type {
          node {
            name { value }
            manufacturer { node { name { value } } }
            platform {
              node {
                netmiko_device_type { value }
                napalm_driver { value }
              }
            }
          }
        }
        primary_address {
          node {
            address { value }
          }
        }
        device_services {
          edges {
            node {
              __typename
              name { value }
              status { value }
              ... on ServiceBGP {
                local_as { node { asn { value } } }
                remote_as { node { asn { value } } }
                router_id { node { address { value } } }
                peer_group {
                  node {
                    name { value }
                    peer_group_type { value }
                  }
                }
              }
              ... on ServiceOSPF {
                process_id { value }
                version { value }
                router_id { node { address { value } } }
                area { node { area { value } name { value } } }
              }
            }
          }
        }
        interfaces {
          edges {
            node {
              id
              name { value }
              description { value }
              status { value }
              role { value }
              ... on InterfacePhysical {
                mtu { value }
                ip_addresses {
                  edges {
                    node {
                      address { value }
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

### Transform: `transforms/spine.py`

```python
from typing import Any
from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader
from netutils.utils import jinja2_convenience_function
from .common import get_data, get_interfaces, get_bgp_profile, get_loopbacks, get_ospf


class Spine(InfrahubTransform):
    query = "spine_config"

    async def transform(self, data: Any) -> str:
        data = get_data(data)

        # Get platform for template selection
        platform = data["device_type"]["platform"]["netmiko_device_type"]

        # Set up Jinja2 environment
        template_path = f"{self.root_directory}/templates/configs/spines"
        env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=False,
        )
        env.filters.update(jinja2_convenience_function())

        # Select platform-specific template
        template = env.get_template(f"{platform}.j2")

        # Prepare template context
        bgp_profiles = get_bgp_profile(data.get("device_services"))
        ospf_configs = get_ospf(data.get("device_services"))

        bgp = {}
        if bgp_profiles:
            first = bgp_profiles[0]
            router_id = first.get("router_id", {}).get("address", "")
            if router_id and "/" in router_id:
                router_id = router_id.split("/")[0]
            bgp = {
                "local_as": first.get("local_as", {}).get("asn", ""),
                "router_id": router_id,
                "neighbors": [],
            }
            for profile in bgp_profiles:
                for session in profile.get("sessions", []):
                    bgp["neighbors"].append({
                        "name": session.get("name", ""),
                        "remote_ip": session.get(
                            "remote_ip", {}
                        ).get("address", ""),
                        "remote_as": session.get(
                            "remote_as", {}
                        ).get("asn", ""),
                    })

        config = {
            "hostname": data.get("name"),
            "bgp": bgp,
            "bgp_profiles": bgp_profiles,
            "ospf": ospf_configs[0] if ospf_configs else {},
            "interfaces": get_interfaces(data.get("interfaces")),
            "loopbacks": get_loopbacks(data.get("interfaces")),
        }

        return template.render(**config)
```

### Config: `.infrahub.yml`

```yaml
queries:
  - name: spine_config
    file_path: queries/config/spine.gql

python_transforms:
  - name: spine
    class_name: Spine
    file_path: transforms/spine.py

artifact_definitions:
  - name: spine_config
    artifact_name: spine
    content_type: text/plain
    targets: spines
    transformation: spine
    parameters:
      device: name__value
```

---

## 2. CSV Cable Matrix Transform

A Python Transformation that generates CSV cable
documentation from topology data.

### Transform: `transforms/topology_cabling.py`

```python
from infrahub_sdk.transforms import InfrahubTransform


class TopologyCabling(InfrahubTransform):
    query = "topology_cabling"

    async def transform(self, data: dict) -> str:
        csv_rows = []
        header = "Source Device,Source Interface,Remote Device,Remote Interface,"
        header += "Cable Type,Cable Status,Cable Color,Cable Label"
        csv_rows.append(header)

        seen_connections = set()

        for device in data["TopologyDataCenter"]["edges"][0]["node"]["devices"]["edges"]:
            source_device = device["node"]["name"]["value"]

            for interface in device["node"]["interfaces"]["edges"]:
                cable = interface["node"].get("connector", {}).get("node")
                if not cable:
                    continue

                source_interface = interface["node"]["name"]["value"]
                cable_type = cable.get("cable_type", {}).get("value", "")
                cable_status = cable.get("status", {}).get("value", "")
                cable_color = cable.get("color", {}).get("value", "")
                cable_label = cable.get("label", {}).get("value", "")

                # Find remote endpoint
                endpoints = cable.get("connected_endpoints", {}).get("edges", [])
                remote_endpoint = None
                for ep in endpoints:
                    ep_node = ep.get("node", {})
                    ep_device = (
                        ep_node.get("device", {})
                        .get("node", {})
                        .get("name", {})
                        .get("value")
                    )
                    ep_intf = ep_node.get("name", {}).get("value")
                    if (ep_device != source_device
                            or ep_intf != source_interface):
                        remote_endpoint = ep_node
                        break

                if not remote_endpoint:
                    continue

                remote_device = (
                    remote_endpoint.get("device", {})
                    .get("node", {})
                    .get("name", {})
                    .get("value")
                )
                remote_interface = remote_endpoint.get("name", {}).get("value")

                # Deduplicate connections
                key = tuple(sorted([
                    (source_device, source_interface),
                    (remote_device, remote_interface),
                ]))
                if key in seen_connections:
                    continue
                seen_connections.add(key)

                row = [source_device, source_interface, remote_device, remote_interface,
                       cable_type, cable_status, cable_color, cable_label]
                escaped = [f'"{f}"' if "," in str(f) else str(f) for f in row]
                csv_rows.append(",".join(escaped))

        return "\n".join(csv_rows)
```

### CSV Cable Matrix Config: `.infrahub.yml`

```yaml
python_transforms:
  - name: topology_cabling
    class_name: TopologyCabling
    file_path: transforms/topology_cabling.py

artifact_definitions:
  - name: Cable matrix for Topology
    artifact_name: topology-cabling
    content_type: text/csv
    targets: topologies_dc
    transformation: topology_cabling
    parameters:
      name: name__value
```

---

## 3. Jinja2 Transform (ContainerLab Topology)

A pure Jinja2 transform for generating ContainerLab topology files.

### ContainerLab Config: `.infrahub.yml`

```yaml
queries:
  - name: topology_simulator
    file_path: queries/topology/clab.gql

jinja2_transforms:
  - name: topology_clab
    description: Template to generate a containerlab topology
    query: topology_simulator
    template_path: templates/clab_topology.j2

artifact_definitions:
  - name: Containerlab Topology
    artifact_name: containerlab-topology
    content_type: text/plain
    targets: topologies_clab
    transformation: topology_clab
    parameters:
      name: name__value
```

### Template: `templates/clab_topology.j2`

```jinja2
name: {{ data.TopologyDataCenter.edges[0].node.name.value }}
topology:
  nodes:
{% for device in data.TopologyDataCenter.edges[0].node.devices.edges %}
    {{ device.node.name.value }}:
      kind: linux
{%- set img = device.node.device_type.node.platform -%}
      image: {{ img.node.containerlab_image.value }}
{% endfor %}
  links:
{% for device in data.TopologyDataCenter.edges[0].node.devices.edges %}
{% for intf in device.node.interfaces.edges %}
{% if intf.node.connector is defined and intf.node.connector.node %}
    - endpoints:
        - "{{ device.node.name.value }}:{{ intf.node.name.value }}"
{%- set cable = intf.node.connector.node -%}
{%- for ep in cable.connected_endpoints.edges %}
{%- if ep.node.device.node.name.value != device.node.name.value or ep.node.name.value != intf.node.name.value %}
        - "{{ ep.node.device.node.name.value }}:{{ ep.node.name.value }}"
{%- endif %}
{%- endfor %}
{% endif %}
{% endfor %}
{% endfor %}
```

---

## 4. Minimal Python Transform Template

The simplest possible Python transform:

### Transform: `transforms/simple.py`

```python
from infrahub_sdk.transforms import InfrahubTransform


class SimpleTransform(InfrahubTransform):
    query = "my_query"

    async def transform(self, data: dict) -> dict:
        device = data["DcimDevice"]["edges"][0]["node"]
        return {
            "hostname": device["name"]["value"],
            "status": device["status"]["value"],
        }
```

### Minimal Transform Config: `.infrahub.yml`

```yaml
queries:
  - name: my_query
    file_path: queries/my_query.gql

python_transforms:
  - name: simple_transform
    class_name: SimpleTransform
    file_path: transforms/simple.py
```

---

## 5. Shared Transform Utilities

### `transforms/common.py`

```python
from typing import Any


def clean_data(data: Any) -> Any:
    """Recursively normalize Infrahub API data."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                keys = set(value.keys())
                if keys == {"value"}:
                    result[key] = value["value"]
                elif keys == {"edges"} and not value["edges"]:
                    result[key] = []
                elif "node" in value:
                    result[key] = clean_data(value["node"])
                elif "edges" in value:
                    result[key] = clean_data(value["edges"])
                else:
                    result[key] = clean_data(value)
            elif "__" in key:
                result[key.replace("__", "")] = value
            else:
                result[key] = clean_data(value)
        return result
    if isinstance(data, list):
        return [clean_data(item.get("node", item)) for item in data]
    return data


def get_data(data: Any) -> Any:
    """Extract the first object from cleaned data."""
    cleaned = clean_data(data)
    first_key = next(iter(cleaned))
    first_value = cleaned[first_key]
    if isinstance(first_value, list) and first_value:
        return first_value[0]
    return first_value if first_value is not None else {}


def get_interfaces(interfaces: list | None) -> list:
    """Return sorted interface list."""
    if not interfaces:
        return []
    return sorted(interfaces, key=lambda x: x.get("name", ""))


def get_loopbacks(interfaces: list | None) -> dict:
    """Map loopback interfaces to their IPs."""
    if not interfaces:
        return {}
    loopbacks = {}
    for intf in interfaces:
        if intf.get("role") == "loopback":
            ips = intf.get("ip_addresses", [])
            if ips:
                loopbacks[intf["name"]] = ips[0].get("address", "")
    return loopbacks


def get_bgp_profile(services: list | None) -> list:
    """Extract BGP service configurations."""
    if not services:
        return []
    return [s for s in services if s.get("typename") == "ServiceBGP"]


def get_ospf(services: list | None) -> list:
    """Extract OSPF service configurations."""
    if not services:
        return []
    return [s for s in services if s.get("typename") == "ServiceOSPF"]


def get_interface_roles(interfaces: list | None) -> dict:
    """Group interfaces by role."""
    if not interfaces:
        return {}
    roles: dict[str, list] = {}
    for intf in interfaces:
        role = intf.get("role", "unknown")
        roles.setdefault(role, []).append(intf)
    return roles
```

---

## 6. Test Definitions for Transforms

YAML-driven tests using the [Resources Testing Framework](../infrahub-common/rules/testing-resource-framework.md). Always create tests alongside new transforms.

### `tests/test_transforms.yml`

```yaml
---
version: "1.0"
infrahub_tests:
  # Python transform: Spine config
  - resource: PythonTransform
    resource_name: spine
    tests:
      - name: smoke_spine
        spec:
          kind: python-transform-smoke

      - name: unit_spine
        spec:
          kind: python-transform-unit-process
          directory: fixtures/spine_transform
          output: output.txt
        expect: PASS

  # Python transform: Simple
  - resource: PythonTransform
    resource_name: simple_transform
    tests:
      - name: smoke_simple
        spec:
          kind: python-transform-smoke

      - name: unit_simple
        spec:
          kind: python-transform-unit-process
          directory: fixtures/simple_transform
        expect: PASS

  # Python transform: CSV Cable Matrix
  - resource: PythonTransform
    resource_name: topology_cabling
    tests:
      - name: smoke_cabling
        spec:
          kind: python-transform-smoke

      - name: unit_cabling
        spec:
          kind: python-transform-unit-process
          directory: fixtures/topology_cabling
          output: output.csv
        expect: PASS

  # Jinja2 transform: ContainerLab Topology
  - resource: Jinja2Transform
    resource_name: topology_clab
    tests:
      - name: smoke_clab
        spec:
          kind: jinja2-transform-smoke

      - name: unit_clab_render
        spec:
          kind: jinja2-transform-unit-render
          directory: fixtures/clab_topology
          output: output.yml
        expect: PASS
```

### Fixture: `tests/fixtures/simple_transform/input.json`

```json
{
  "DcimDevice": {
    "edges": [
      {
        "node": {
          "name": { "value": "spine-01" },
          "status": { "value": "active" }
        }
      }
    ]
  }
}
```

### Fixture: `tests/fixtures/clab_topology/input.json`

```json
{
  "TopologyDataCenter": {
    "edges": [
      {
        "node": {
          "name": { "value": "dc-topology-01" },
          "devices": {
            "edges": [
              {
                "node": {
                  "name": { "value": "spine-01" },
                  "device_type": {
                    "node": {
                      "platform": {
                        "node": { "containerlab_image": { "value": "ceos:latest" } }
                      }
                    }
                  },
                  "interfaces": { "edges": [] }
                }
              }
            ]
          }
        }
      }
    ]
  }
}
```

### Fixture: `tests/fixtures/clab_topology/output.yml`

```yaml
name: dc-topology-01
topology:
  nodes:
    spine-01:
      kind: linux
      image: ceos:latest
  links:
```

---

## 6. SVG Diagram Artifact (`image/svg+xml`)

Every other example here uses `text/plain` or
`text/csv`. This one exists because `image/svg+xml` is
the content type most often assumed unsupported: it is
the only one of the eight that is not text, so scanning
examples gives the wrong answer. It is supported, and an
artifact can deliver a generated diagram.

The shape to remember: **the transform returns a
string.** Only `application/json` and `application/yaml`
special-case a `dict`; every other content type passes
the payload through `str()`, so returning a dict here
would write a Python repr into the artifact body with no
error. See
[rules/artifacts-definitions.md](./rules/artifacts-definitions.md).

### Query: `queries/topology/rack_elevation.gql`

```graphql
query RackElevation($rack: String!) {
  LocationRack(name__value: $rack) {
    edges {
      node {
        name { value }
        height { value }
        devices {
          edges {
            node {
              name { value }
              position { value }
              device_type {
                node {
                  height { value }
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

### Transform: `transforms/rack_elevation.py`

```python
from infrahub_sdk.transforms import InfrahubTransform

UNIT_HEIGHT = 20
UNIT_WIDTH = 220
MARGIN = 40


class RackElevation(InfrahubTransform):
    query = "rack_elevation"

    async def transform(self, data: dict) -> str:
        """Return an SVG rack elevation.

        Returns a str, not a dict: `image/svg+xml` is serialised with
        `str()`, so a dict would be stored as its Python repr.
        """
        rack = data["LocationRack"]["edges"][0]["node"]
        units = rack["height"]["value"]
        height = units * UNIT_HEIGHT + 2 * MARGIN
        width = UNIT_WIDTH + 2 * MARGIN

        parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            f'<rect x="{MARGIN}" y="{MARGIN}" width="{UNIT_WIDTH}" '
            f'height="{units * UNIT_HEIGHT}" fill="none" stroke="#333"/>',
        ]

        # Rack unit 1 is at the bottom, so invert for screen coordinates.
        for u in range(units):
            y = MARGIN + (units - u - 1) * UNIT_HEIGHT
            parts.append(
                f'<text x="{MARGIN - 8}" y="{y + 14}" font-size="10" '
                f'text-anchor="end" fill="#888">{u + 1}</text>'
            )

        for edge in rack["devices"]["edges"]:
            device = edge["node"]
            position = device["position"]["value"]
            if position is None:
                continue  # unracked device: nothing to draw
            span = device["device_type"]["node"]["height"]["value"] or 1
            y = MARGIN + (units - position - span + 1) * UNIT_HEIGHT
            parts.append(
                f'<rect x="{MARGIN}" y="{y}" width="{UNIT_WIDTH}" '
                f'height="{span * UNIT_HEIGHT}" fill="#cfe3f7" stroke="#333"/>'
            )
            parts.append(
                f'<text x="{MARGIN + 8}" y="{y + 14}" font-size="11">'
                f'{_escape(device["name"]["value"])}</text>'
            )

        parts.append("</svg>")
        return "\n".join(parts)


def _escape(value: str) -> str:
    """Escape the five XML entities. Device names carry `&` and `<` in practice."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
```

### Config: `.infrahub.yml`

```yaml
---
queries:
  - name: rack_elevation
    file_path: "queries/topology/rack_elevation.gql"

python_transforms:
  - name: rack_elevation
    class_name: RackElevation
    file_path: "transforms/rack_elevation.py"

artifact_definitions:
  - name: rack_elevation
    artifact_name: "Rack Elevation"
    content_type: image/svg+xml       # not text/plain — the artifact IS a diagram
    targets: racks                    # group of LocationRack objects
    transformation: rack_elevation    # exact-name match to the transform above
    parameters:
      rack: name__value               # each target's name into $rack
```

The target group's members must inherit
`CoreArtifactTarget` on the concrete node, as with any
artifact:

```yaml
nodes:
  - name: Rack
    namespace: Location
    inherit_from:
      - CoreArtifactTarget
```

### Why a Python transform rather than Jinja2

Either works, and Jinja2 is the cheaper layer when the
output is a fixed shape with values substituted in. Pick
Python when the geometry has to be *computed* — here the
`y` coordinate depends on rack height, device position
and device height together, and units are numbered bottom
-up while SVG coordinates run top-down. Expressing that
arithmetic in a template is where a Jinja2 diagram
template stops being readable.

If your diagram is a static layout with substituted
labels, register it under `jinja2_transforms` instead and
keep the same `artifact_definitions` entry.

---

## Complete File Structure

```text
project/
  .infrahub.yml
  transforms/
    __init__.py
    common.py                    # Shared utilities
    spine.py                     # Spine config (Python + Jinja2)
    leaf.py                      # Leaf config
    topology_cabling.py          # Cable matrix CSV
  templates/
    configs/
      spines/
        arista_eos.j2
        cisco_nxos.j2
        juniper_junos.j2
      leafs/
        arista_eos.j2
    clab_topology.j2
  queries/
    config/
      spine.gql
      leaf.gql
    topology/
      clab.gql
      cabling.gql
  tests/
    test_transforms.yml          # Test definitions (smoke + unit)
    fixtures/
      spine_transform/
        input.json
        output.txt
      simple_transform/
        input.json
      clab_topology/
        input.json
        output.yml
      topology_cabling/
        input.json
        output.csv
```
