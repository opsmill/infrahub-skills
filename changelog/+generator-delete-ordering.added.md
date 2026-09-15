`infrahub-managing-generators` now covers delete ordering: detach peers from a relationship
and save before deleting the peer nodes. A node's relationship manager reads only its own
in-memory peer list, so a `save()` issued after a peer's `.delete()` re-sends the dead peer's
id. Build the id list first, because `remove()` pops from the same list `.peers` hands back,
so driving the detach loop off `.peers` skips every other element.
