# Infrahub Generator Examples

Real-world examples extracted from production Infrahub
repositories.

---

## 1. POP Topology Generator

Creates network infrastructure for a colocation center from
a topology design object.

### Query: `queries/topology/pop.gql`

```graphql
query device($name: String!) {
  TopologyColocationCenter(name__value: $name) {
    edges {
      node {
        id
        name { value }
        description { value }
        management_subnet {
          node {
            id
            prefix { value }
          }
        }
        technical_subnet {
          node {
            id
            prefix { value }
          }
        }
        location {
          node { id }
        }
        design {
          node {
            name { value }
            elements {
              edges {
                node {
                  ... on DesignElement {
                    quantity { value }
                    role { value }
                    template {
                      node {
                        id
                        template_name { value }
                        __typename
                        ... on TemplateDcimDevice {
                          interfaces {
                            edges {
                              node {
                                ... on TemplateInterfacePhysical {
                                  name { value }
                                  role { value }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                    device_type {
                      node {
                        id
                        manufacturer {
                          node { name { value } }
                        }
                        platform {
                          node { id }
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
  }
}
```

### Generator: `generators/generate_pop.py`

```python
from infrahub_sdk.generator import InfrahubGenerator
from .common import TopologyCreator, clean_data


class PopTopologyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Clean the GraphQL response
        cleaned_data = clean_data(data)
        topology = cleaned_data[
            "TopologyColocationCenter"
        ][0]

        # Initialize the topology creator helper
        creator = TopologyCreator(
            client=self.client,
            log=self.logger,
            branch=self.branch,
            data=topology,
        )

        # Load and prepare topology data
        await creator.load_data()

        # Create infrastructure in dependency order
        await creator.create_site()

        # Set up IP address pools
        subnets = []
        if topology.get("management_subnet"):
            subnets.append({
                "type": "Management",
                "prefix_id": topology[
                    "management_subnet"
                ]["id"],
            })
        if topology.get("technical_subnet"):
            subnets.append({
                "type": "Loopback",
                "prefix_id": topology[
                    "technical_subnet"
                ]["id"],
            })
        await creator.create_address_pools(subnets)

        # Create VLAN pool
        await creator.create_L2_pool()

        # Create devices with interfaces
        await creator.create_devices()

        # Create loopback interfaces
        await creator.create_loopback("loopback0")

        # Create OOB connections
        await creator.create_oob_connections("management")
        await creator.create_oob_connections("console")
```

### Config: `.infrahub.yml`

```yaml
queries:
  - name: topology_pop
    file_path: queries/topology/pop.gql

generator_definitions:
  - name: create_pop
    file_path: generators/generate_pop.py
    # CoreGeneratorGroup containing topology objects
    targets: topologies_pop
    query: topology_pop
    class_name: PopTopologyGenerator
    parameters:
      name: name__value
```

---

## 2. Network Segment Generator

Creates VxLAN/VLAN configuration from a service network
segment definition.

### Query: `queries/segment/segment.gql`

```graphql
query segment($name: String!) {
  ServiceNetworkSegment(name__value: $name) {
    edges {
      node {
        id
        name { value }
        customer_name { value }
        environment { value }
        segment_type { value }
        vlan_id { value }
        status { value }
        owner {
          node {
            id
            name { value }
          }
        }
        deployment {
          node {
            id
            name { value }
            ... on TopologyDataCenter {
              devices {
                edges {
                  node {
                    id
                    name { value }
                    ... on DcimDevice {
                      role { value }
                    }
                  }
                }
              }
            }
          }
        }
        prefix {
          node {
            id
            prefix { value }
          }
        }
      }
    }
  }
}
```

### Generator: `generators/generate_segment.py`

```python
from infrahub_sdk.generator import InfrahubGenerator
from .common import clean_data


class NetworkSegmentGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        cleaned = clean_data(data)
        segment = cleaned["ServiceNetworkSegment"][0]

        segment_name = segment["name"]
        vlan_id = segment.get("vlan_id")

        # Calculate VNI from VLAN ID
        vni = vlan_id + 10000 if vlan_id else None

        # Calculate Route Distinguisher
        rd = f"65000:{vlan_id}" if vlan_id else None

        # Get leaf devices from the deployment topology
        deployment = segment.get("deployment", {})
        devices = deployment.get("devices", [])
        leaf_devices = [
            d for d in devices
            if d.get("role") == "leaf"
        ]

        # Create VLAN object
        vlan = await self.client.create(
            kind="IpamVLAN",
            data={
                "name": segment_name,
                "vlan_id": vlan_id,
                "status": "active",
            }
        )
        await vlan.save(allow_upsert=True)

        # Associate segment with leaf device interfaces
        for device in leaf_devices:
            # Create interface-to-segment mapping
            mapping = await self.client.create(
                kind="ServiceSegmentDeployment",
                data={
                    "segment": segment["id"],
                    "device": device["id"],
                    "vni": vni,
                    "route_distinguisher": rd,
                }
            )
            await mapping.save(allow_upsert=True)
```

---

## 3. Minimal Generator Template

The simplest possible generator:

### Query: `queries/widget.gql`

```graphql
query widget($name: String!) {
  MyWidget(name__value: $name) {
    edges {
      node {
        id
        name { value }
        count { value }
      }
    }
  }
}
```

### Generator: `generators/widget_gen.py`

```python
from infrahub_sdk.generator import InfrahubGenerator


class WidgetGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        widget = data["MyWidget"]["edges"][0]["node"]
        widget_name = widget["name"]["value"]
        count = widget["count"]["value"]

        for i in range(1, count + 1):
            resource = await self.client.create(
                kind="MyResource",
                data={
                    "name": (
                        f"{widget_name}-resource-{i:02d}"
                    ),
                },
            )
            await resource.save(allow_upsert=True)
```

### Minimal Config: `.infrahub.yml`

```yaml
queries:
  - name: widget_query
    file_path: queries/widget.gql

generator_definitions:
  - name: widget_generator
    file_path: generators/widget_gen.py
    query: widget_query
    targets: widgets
    class_name: WidgetGenerator
    parameters:
      name: name__value
```

---

## 4. Generator with convert_query_response

When `convert_query_response: true`, the GraphQL response is
converted to SDK `InfrahubNode` objects accessible via
`self.nodes`:

```python
from infrahub_sdk.generator import InfrahubGenerator


class TypedGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # With convert_query_response=True, use self.nodes
        widget = self.nodes[0]

        # Access attributes via .value
        name = widget.name.value
        count = widget.count.value

        for i in range(1, count + 1):
            resource = await self.client.create(
                kind="MyResource",
                data={"name": f"{name}-{i:02d}"},
            )
            await resource.save(allow_upsert=True)
```

```yaml
generator_definitions:
  - name: typed_generator
    file_path: generators/typed_gen.py
    query: widget_query
    targets: widgets
    class_name: TypedGenerator
    # Enable SDK object conversion
    convert_query_response: true
    parameters:
      name: name__value
```

---

## 5. Modular Cascade (Two Generators)

A cascade splits work across hierarchy layers. Here, an
upstream generator creates devices from a topology design;
a downstream generator allocates management interfaces per
device. The downstream skips work when its inputs haven't
changed.

### Downstream schema: device inherits GeneratorTarget

```yaml
nodes:
  - name: Device
    namespace: Dcim
    inherit_from:
      - GeneratorTarget
    attributes:
      - name: name
        kind: Text
      - name: role
        kind: Text
    relationships:
      - name: mgmt_interface
        peer: DcimInterfaceManagement
        kind: Component
        cardinality: one
        optional: true
```

The `checksum` attribute comes from `GeneratorTarget` — no
need to declare it.

### Upstream generator: creates devices

```python
# generators/generate_devices.py
from infrahub_sdk.generator import InfrahubGenerator


class DeviceGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        topology = data["TopologyDataCenter"]["edges"][0]["node"]
        design = topology["design"]["node"]
        expected = design["expected_element_count"]["value"]
        elements = design["elements"]["edges"]

        if len(elements) != expected:
            raise ValueError(
                f"Incomplete upstream data: expected {expected} "
                f"elements, got {len(elements)}"
            )

        topology_name = topology["name"]["value"]
        for element in sorted(
            elements, key=lambda e: e["node"]["role"]["value"]
        ):
            quantity = element["node"]["quantity"]["value"]
            role = element["node"]["role"]["value"]
            for i in range(1, quantity + 1):
                device = await self.client.create(
                    kind="DcimDevice",
                    data={"name": f"{topology_name}-{role}-{i:02d}"},
                )
                await device.save(allow_upsert=True)
```

Notice: this generator creates exactly one kind
(`DcimDevice`) and writes nothing to `checksum` — it's the
upstream, not the downstream.

### Downstream generator: allocates mgmt interfaces with checksum guard

```python
# generators/generate_mgmt_interfaces.py
import hashlib

from infrahub_sdk.generator import InfrahubGenerator


GENERATOR_VERSION = "1"


class MgmtInterfaceGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        devices = data["DcimDevice"]["edges"]
        expected = data.get("expected_count", {}).get("value", len(devices))

        if len(devices) != expected:
            raise ValueError(
                f"Incomplete upstream: expected {expected} devices, "
                f"got {len(devices)}"
            )

        for edge in sorted(devices, key=lambda e: e["node"]["id"]):
            device = edge["node"]

            # Compute a checksum over the inputs this run depends on
            inputs = f"v{GENERATOR_VERSION}:{device['id']}:{device['name']['value']}"
            new_checksum = hashlib.sha256(inputs.encode()).hexdigest()

            if device["checksum"]["value"] == new_checksum:
                continue  # downstream already in sync — skip

            iface = await self.client.create(
                kind="DcimInterfaceManagement",
                data={
                    "device": device["id"],
                    "name": "mgmt0",
                },
            )
            await iface.save(allow_upsert=True)

            # Record the new checksum on the upstream device so the
            # cascade settles on the next no-op run.
            device_obj = await self.client.get(
                kind="DcimDevice", id=device["id"],
            )
            device_obj.checksum.value = new_checksum
            await device_obj.save(allow_upsert=True)
```

Notice:

- Single `kind` (`DcimInterfaceManagement`) — one layer per
  generator.
- `GENERATOR_VERSION` prefixed into the hash so a logic
  change forces re-cascade on the next run.
- The guard (`if device["checksum"]["value"] == new_checksum:
  continue`) is what makes this a true cascade rather than
  just two generators that happen to run in sequence.

### Registration

```yaml
# .infrahub.yml
generator_definitions:
  - name: generate_devices
    file_path: generators/generate_devices.py
    query: dc_topology
    targets: dc_topologies
    class_name: DeviceGenerator
  - name: generate_mgmt_interfaces
    file_path: generators/generate_mgmt_interfaces.py
    query: devices_for_mgmt
    targets: devices_needing_mgmt
    class_name: MgmtInterfaceGenerator
```

---

## Complete File Structure

```text
project/
  .infrahub.yml
  generators/
    __init__.py
    common.py              # TopologyCreator, clean_data
    generate_dc.py         # DC topology generator
    generate_pop.py        # POP topology generator
    generate_segment.py    # Network segment generator
  queries/
    topology/
      dc.gql
      pop.gql
    segment/
      segment.gql
```
