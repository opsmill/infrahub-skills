```python
from infrahub_sdk.generator import InfrahubGenerator


class RackLeaf(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        rack = data["LocationRack"]["edges"][0]["node"]
        name = f"leaf-{rack['name']['value']}"
        leaf = await self.client.create(kind="DcimDevice", data={"name": name, "rack": rack["id"]})
        await leaf.save(allow_upsert=True, update_group_context=False)
        tag = await self.client.create(kind="OpsAssetTag", data={"name": f"asset-{name}"})
        await tag.save(allow_upsert=True)
```
