Raises on an empty query result, with a comment saying why.

```python
from infrahub_sdk.generator import InfrahubGenerator


class RackLeafGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        racks = data["LocationRack"]["edges"]
        # Fail rather than return: a run that saves nothing deletes the leaf.
        if not racks:
            raise ValueError("rack_leaf returned no rack")
        rack = racks[0]["node"]
        name = f"leaf-{rack['name']['value']}"
        tag = await self.client.create(kind="OpsAssetTag", data={"name": f"asset-{name}"})
        await tag.save(allow_upsert=True, update_group_context=False)
        leaf = await self.client.create(kind="DcimDevice", data={"name": name, "rack": rack["id"], "asset_tag": tag.id})
        await leaf.save(allow_upsert=True)
```
