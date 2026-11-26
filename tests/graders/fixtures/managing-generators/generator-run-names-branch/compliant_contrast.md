From infrahub-sdk 1.24.0 the Git checkout no longer selects the branch.

```bash
# WRONG: no branch, so the run targets main
infrahubctl generator pop_topology design=pop-par-02
```

```bash
# RIGHT
infrahubctl generator pop_topology design=pop-par-02 --branch pop-par-02-design
```
