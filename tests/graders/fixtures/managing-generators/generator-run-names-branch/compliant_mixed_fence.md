Both forms in one block, the wrong one first.

```bash
# WRONG: no branch
infrahubctl generator pop_topology design=pop-par-02

# RIGHT
infrahubctl generator pop_topology design=pop-par-02 --branch pop-par-02-design
```
