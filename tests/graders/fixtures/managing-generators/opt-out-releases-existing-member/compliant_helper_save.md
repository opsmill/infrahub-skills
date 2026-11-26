The trunk is saved with the opt-out through a shared helper, then removed from the group.

```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def _save(self, node) -> None:
        await node.save(allow_upsert=True, update_group_context=False)

    async def generate(self, data: dict) -> None:
        trunk = await self.client.create(kind="NetContainer", data={"name": "shared-trunk"})
        await self._save(trunk)
        group = await self.client.group_context.get_group()
        await group.remove_relationships(relation_to_update="members", related_nodes=[trunk.id])
        segment = await self.client.create(kind="NetSegment", data={"name": "s1", "parent": trunk.id})
        await segment.save(allow_upsert=True)
```
