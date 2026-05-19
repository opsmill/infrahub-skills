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
