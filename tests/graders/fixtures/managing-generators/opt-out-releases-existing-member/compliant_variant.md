```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def _release(self, node_id: str) -> None:
        group = await self.client.group_context.get_group()
        if group is not None:
            await group.remove_relationships("members", [node_id])

    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]
        trunk = await self.client.get(kind="NetContainer", name__value="shared-trunk")
        await self._release(trunk.id)
        for leg in service["legs"]["edges"]:
            segment = await self.client.create(
                kind="NetSegment", data={"name": leg["node"]["name"]["value"]},
            )
            await segment.save(allow_upsert=True)
            await trunk.add_relationships(relation_to_update="children", related_nodes=[segment.id])
```
