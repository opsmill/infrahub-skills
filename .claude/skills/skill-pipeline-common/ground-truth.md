# Ground truth ladder

Run this before writing any root cause, and against any Infrahub behavior
claim in a feature idea. It answers two questions, not one: is the claim true,
and true at which version.

## Is the claim true at version V?

Work down the ladder and stop at the first rung that answers the claim.

1. Local `opsmill/infrahub` checkout, read with `git show <tag>:<path>`.
   Never check out the tag, never touch the working tree, never assume the
   clone is sitting on the right branch.
2. Installed `infrahub-sdk` in the project virtualenv, for SDK surface claims.
3. Mark the claim `UNVERIFIED` and carry on. Do not stop the pipeline for it.

GitHub at the tag is a fourth rung, run only when the user passes `--fetch`
or asks directly. `UNVERIFIED` is already an accepted outcome, so the network
round trip, the auth, and the rate limit are not worth paying by default.

## Finding the local checkout

```bash
# Candidate paths, first hit wins. Stop at the first that is a git repo
# whose origin is opsmill/infrahub.
for d in ~/dev/opsmill/infrahub ~/opsmill/infrahub ~/src/infrahub; do
  git -C "$d" remote get-url origin 2>/dev/null | grep -q 'opsmill/infrahub\(\.git\)\?$' && { echo "$d"; break; }
done
```

If none match, ask the user for the path once, then fall back to rung 2.

## Reading at a version

```bash
REPO=<path from above>
TAG=$(git -C "$REPO" tag --list 'infrahub-v*' --sort=-v:refname | head -1)   # or the pinned --infrahub value
git -C "$REPO" fetch --tags --quiet
git -C "$REPO" show "$TAG:backend/infrahub/<path>" | head -200
git -C "$REPO" rev-parse "$TAG"
```

`git show` never touches the working tree, which is why it is the only read
allowed here. Confirm the tag pattern against
`git -C "$REPO" tag --list | tail -5` before relying on it, since tag naming
is the repository's choice and not this file's to assume.

## Read cap

Read at most 5 files and 200 lines each per claim. On hitting the cap, say so
in the handoff and mark the claim `UNVERIFIED` rather than silently
truncating.

## Was it already fixed upstream?

If the guidance was correct for an older release and Infrahub has since
changed, the fix is a version scoped rule, not a correction. Compare the
claim against the pinned version and against the latest tag when they differ.

## When ground truth contradicts the report

If the current guidance is right, stop and report that. Do not invent a fix
to justify the investigation.
