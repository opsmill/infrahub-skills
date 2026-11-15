```python
from infrahub_sdk.generator import InfrahubGenerator


class RackLeaf(InfrahubGenerator):
    async def _save_tag(self) -> None:
        await self.tag.save(allow_upsert=True, update_group_context=False)

    async def generate(self, data: dict) -> None:
        rack = data["LocationRack"]["edges"][0]["node"]
        name = f"leaf-{rack['name']['value']}"
        self.tag = await self.client.create(kind="OpsAssetTag", data={"name": f"asset-{name}"})
        await self._save_tag()
        leaf = await self.client.create(
            kind="DcimDevice", data={"name": name, "rack": rack["id"], "asset_tag": self.tag.id}
        )
        await leaf.save(allow_upsert=True)
```
