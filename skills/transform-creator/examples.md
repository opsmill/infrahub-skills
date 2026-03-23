# Infrahub Transform Examples

Real-world examples extracted from production Infrahub repositories.

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
```
