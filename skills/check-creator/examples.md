# Infrahub Check Examples

Real-world examples extracted from production Infrahub
repositories.

---

## 1. Global Check: Rack Unit Collision Detection

A global check that validates all devices across all racks
don't have conflicting positions.

### Global Query: `queries/rack_devices.gql`

```graphql
query RackDevices {
  DcimGenericDevice {
    edges {
      node {
        id
        __typename
        display_label
        name {
          value
        }
        rack_u_position {
          value
        }
        rack_face {
          value
        }
        rack {
          node {
            id
            display_label
            name {
              value
            }
          }
        }
        device_type {
          node {
            id
            model {
              value
            }
            u_height {
              value
            }
            is_full_depth {
              value
            }
          }
        }
      }
    }
  }
}
```

### Global Check: `checks/rack_unit_collision.py`

```python
from collections import defaultdict
from infrahub_sdk.checks import InfrahubCheck


class RackUnitCollisionCheck(InfrahubCheck):
    query = "rack_devices"

    def validate(self, data: dict) -> None:
        edges = (
            data
            .get("DcimGenericDevice", {})
            .get("edges", [])
        )

        # Group devices by rack
        devices_by_rack: dict[str, list[dict]] = (
            defaultdict(list)
        )
        for edge in edges:
            device = edge.get("node", {})
            rack_u_position = (
                device
                .get("rack_u_position", {})
                .get("value")
            )
            if rack_u_position is None:
                continue

            rack_node = (
                device.get("rack", {}).get("node")
            )
            if not rack_node:
                continue

            rack_id = rack_node.get("id")
            device_type = (
                device
                .get("device_type", {})
                .get("node", {})
            )

            device_info = {
                "id": device.get("id"),
                "name": (
                    device.get("display_label")
                    or device
                    .get("name", {})
                    .get("value", "Unknown")
                ),
                "type": device.get(
                    "__typename", "Unknown"
                ),
                "rack_name": rack_node.get(
                    "display_label", "Unknown"
                ),
                "rack_u_position": rack_u_position,
                "u_height": (
                    device_type
                    .get("u_height", {})
                    .get("value", 1) or 1
                ),
                "rack_face": (
                    device
                    .get("rack_face", {})
                    .get("value", "front")
                ),
                "is_full_depth": (
                    device_type
                    .get("is_full_depth", {})
                    .get("value", True)
                ),
            }
            devices_by_rack[rack_id].append(
                device_info
            )

        # Check collisions within each rack
        for rack_id, devices in (
            devices_by_rack.items()
        ):
            for i, dev_a in enumerate(devices):
                rus_a = set(range(
                    dev_a["rack_u_position"],
                    dev_a["rack_u_position"]
                    + dev_a["u_height"],
                ))
                for dev_b in devices[i + 1:]:
                    rus_b = set(range(
                        dev_b["rack_u_position"],
                        dev_b["rack_u_position"]
                        + dev_b["u_height"],
                    ))
                    overlap = rus_a & rus_b
                    if overlap and (
                        dev_a["is_full_depth"]
                        or dev_b["is_full_depth"]
                        or dev_a["rack_face"]
                        == dev_b["rack_face"]
                    ):
                        self.log_error(
                            message=(
                                "RU collision in"
                                f" rack"
                                f" '{dev_a['rack_name']}':"
                                f" '{dev_a['name']}'"
                                " conflicts with"
                                f" '{dev_b['name']}'"
                            ),
                            object_id=dev_a["id"],
                            object_type=(
                                dev_a["type"]
                            ),
                        )
```

### Global Config: `.infrahub.yml`

```yaml
queries:
  - name: rack_devices
    file_path: queries/rack_devices.gql

check_definitions:
  - name: check_rack_unit_collision
    class_name: RackUnitCollisionCheck
    file_path: checks/rack_unit_collision.py
    # No targets = global check
```

---

## 2. Targeted Check: Leaf Device Validation

A targeted check that validates leaf switches have proper
interface configuration.

### Targeted Query: `queries/config/leaf.gql`

```graphql
query leaf_config($device: String!) {
  DcimDevice(name__value: $device) {
    edges {
      node {
        id
        name { value }
        role { value }
        interfaces {
          edges {
            node {
              name { value }
              role { value }
              ... on InterfacePhysical {
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
        device_services {
          edges {
            node {
              __typename
              name { value }
            }
          }
        }
      }
    }
  }
}
```

### Targeted Check: `checks/leaf.py`

```python
from typing import Any
from infrahub_sdk.checks import InfrahubCheck
from .common import get_data, validate_interfaces


class CheckLeaf(InfrahubCheck):
    query = "leaf_config"

    def validate(self, data: Any) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        data = get_data(data)

        # Validate interfaces - critical
        errors.extend(validate_interfaces(data))

        # Check for services
        device_services = (
            data.get("device_services") or []
        )
        if not device_services:
            warnings.append(
                "No services configured on this"
                " device"
            )
        else:
            redundant_bgp = [
                s.get("name")
                for s in device_services
                if s.get("typename") == "ServiceBGP"
            ]
            if (
                redundant_bgp
                and len(redundant_bgp) < 2
            ):
                warnings.append(
                    "BGP redundancy not configured"
                )

        for warning in warnings:
            self.log_info(
                message=f"WARNING: {warning}"
            )

        for error in errors:
            self.log_error(message=error)
```

### Shared Utilities: `checks/common.py`

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
                elif (
                    keys == {"edges"}
                    and not value["edges"]
                ):
                    result[key] = []
                elif "node" in value:
                    result[key] = clean_data(
                        value["node"]
                    )
                elif "edges" in value:
                    result[key] = clean_data(
                        value["edges"]
                    )
                else:
                    result[key] = clean_data(value)
            elif "__" in key:
                result[
                    key.replace("__", "")
                ] = value
            else:
                result[key] = clean_data(value)
        return result
    if isinstance(data, list):
        return [
            clean_data(item.get("node", item))
            for item in data
        ]
    return data


def get_data(data: Any) -> Any:
    """Extract first object from cleaned data."""
    cleaned = clean_data(data)
    if isinstance(cleaned, dict) and cleaned:
        first_key = next(iter(cleaned))
        first_value = cleaned[first_key]
        if (
            isinstance(first_value, list)
            and first_value
        ):
            return first_value[0]
        return (
            first_value
            if first_value is not None
            else {}
        )
    raise ValueError(
        "clean_data() did not return"
        " a non-empty dictionary"
    )


def validate_interfaces(
    data: dict[str, Any],
) -> list[str]:
    """Validate device interfaces."""
    errors: list[str] = []
    if len(data.get("interfaces", [])) == 0:
        errors.append(
            "Device has no interfaces configured"
        )

    for intf in data.get("interfaces", []):
        if (
            intf.get("role") == "loopback"
            and not intf.get("ip_addresses")
        ):
            errors.append(
                f"Loopback interface"
                f" {intf.get('name', 'unknown')}"
                " is missing IP address"
            )

    return errors
```

### Targeted Config: `.infrahub.yml`

```yaml
queries:
  - name: leaf_config
    file_path: queries/config/leaf.gql

check_definitions:
  - name: validate_leaf
    class_name: CheckLeaf
    file_path: checks/leaf.py
    targets: leafs    # Only runs against this group
    parameters:
      device: name__value  # $device = target name
```

---

## 3. Minimal Check Template

The simplest possible check structure:

### Minimal Query: `queries/tags.gql`

```graphql
query Tags {
  BuiltinTag {
    edges {
      node {
        id
        name { value }
      }
    }
  }
}
```

### Minimal Check: `checks/tag_naming.py`

```python
import re
from infrahub_sdk.checks import InfrahubCheck

VALID_TAG = re.compile(r"^[a-z][a-z0-9-]+$")


class TagNamingCheck(InfrahubCheck):
    query = "tags"

    def validate(self, data: dict) -> None:
        for edge in data["BuiltinTag"]["edges"]:
            tag = edge["node"]
            tag_name = tag["name"]["value"]
            if not VALID_TAG.match(tag_name):
                self.log_error(
                    message=(
                        f"Invalid tag name"
                        f" '{tag_name}':"
                        " must be lowercase"
                        " alphanumeric with"
                        " hyphens"
                    ),
                    object_id=tag["id"],
                    object_type="BuiltinTag",
                )
```

### Minimal Config: `.infrahub.yml`

```yaml
queries:
  - name: tags
    file_path: queries/tags.gql

check_definitions:
  - name: check_tag_naming
    class_name: TagNamingCheck
    file_path: checks/tag_naming.py
```

---

## Complete File Structure

```text
project/
  .infrahub.yml
  checks/
    __init__.py
    common.py              # Shared utilities
    rack_unit_collision.py  # Global check
    leaf.py                 # Targeted check
    spine.py                # Targeted check
  queries/
    rack_devices.gql        # Global query
    config/
      leaf.gql              # Targeted query
      spine.gql
    validation/
      loadbalancer_validation.gql
```
